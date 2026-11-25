"""Anonimización de datos personales antes de enviar texto a un proveedor de IA externo.

Qué hace: sustituye por marcadores (`[PERSONA_1]`, `[DOCUMENTO_1]`, `[TELEFONO_1]`, `[CORREO_1]`,
`[DIRECCION_1]`, `[NACIMIENTO_1]`) los datos que identifican a una persona y que aparecen con una
etiqueta que los delata («Paciente: …», «CC 1.234.567», «Cel. 300 123 4567», «Cra 15 # 93-60»…).
El mismo valor recibe siempre el mismo marcador, y la respuesta del modelo se restaura con el mapa
de la consulta, de modo que el usuario ve los datos reales y las citas siguen siendo literales.

Qué NO hace (y el consentimiento lo dice): es un enmascarado por patrones, no una garantía.
- Un nombre que aparece SIN etiqueta («…lo atendió Juan Pérez») no se detecta.
- Se descarta a propósito enmascarar números sueltos: en una licitación, un CUM, un registro INVIMA
  o un NIT no son datos de una persona, y taparlos rompería el análisis.

Solo usa la biblioteca estándar. Es determinista y no llama a ningún servicio.
"""

import re
from dataclasses import dataclass, field, replace
from typing import Any

# Etiquetas que delatan un dato personal. La parte entre `(?i: ...)` ignora mayúsculas; las siglas
# (CC, TI, CE) se exigen en mayúsculas para no confundir «ti» (pronombre) con una tarjeta
# de identidad.
_PALABRA = r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+"
_NOMBRE = _PALABRA + r"(?:\s+(?:(?:de|del)\s+(?:la\s+|los\s+|las\s+)?)?" + _PALABRA + r"){0,3}"
_MAYUS = r"[A-ZÁÉÍÓÚÑ]{2,}"
_NOMBRE_MAYUS = _MAYUS + r"(?:\s+" + _MAYUS + r"){1,3}"
_ETIQUETAS_PERSONA = (
    r"(?i:paciente|nombres?(?:\s+completos?)?|apellidos?|acudiente|responsable|familiar|"
    r"madre|padre|esposo|esposa|titular|solicitante|se[ñn]or|se[ñn]ora|sr\.?|sra\.?|"
    r"m[eé]dic[oa]|doctor|doctora|dra?\.|enfermer[oa])"
)

# (tipo, patrón compilado, grupo que se enmascara). Se aplican en este orden.
_REGLAS: list[tuple[str, re.Pattern[str], str | int]] = [
    ("CORREO", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), 0),
    (
        "TELEFONO",
        re.compile(
            r"(?i:tel[eé]fono|tel\.?|celular|cel\.?|m[oó]vil|whatsapp)\s*[:\-]?\s*"
            r"(?P<v>\+?[\d\s().-]{7,18}\d)"
        ),
        "v",
    ),
    (
        "TELEFONO",
        re.compile(r"(?<![\d.])(?:\+?57[\s.-]?)?3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"),
        0,
    ),
    (
        "DOCUMENTO",
        re.compile(
            r"(?:CC|C\.C\.|TI|T\.I\.|CE|C\.E\.|"
            r"(?i:c[eé]dula(?:\s+de\s+ciudadan[ií]a)?|tarjeta\s+de\s+identidad|"
            r"documento(?:\s+de\s+identidad)?|identificaci[oó]n|pasaporte))"
            r"\s*(?:(?i:n[°ºo.]*|no\.?|n[uú]mero))?\s*[:\-]?\s*"
            r"(?P<v>\d{1,3}(?:[.\s]\d{3}){1,3}|\d{6,12})(?!\d)"
        ),
        "v",
    ),
    (
        "DIRECCION",
        re.compile(
            r"\b(?i:calle|carrera|cra|cr|kr|cl|avenida|av|avda|diagonal|diag|transversal|tv|"
            r"circular|autopista)\.?\s*\d+\s*[a-zA-Z]?(?:\s*(?i:bis))?\s*"
            r"(?:#|(?i:n[°ºo.]*|no\.?))\s*\d+\s*[a-zA-Z]?\s*[-–]\s*\d+"
        ),
        0,
    ),
    (
        "NACIMIENTO",
        re.compile(
            r"(?i:fecha\s+de\s+nacimiento|f\.?\s?nac(?:imiento)?\.?|nacid[oa](?:/a)?\s+el|naci[oó]\s+el)"
            r"\s*[:\-]?\s*(?P<v>\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{1,2}\s+de\s+[a-zA-Zé]+\s+de\s+\d{4})"
        ),
        "v",
    ),
    (
        "PERSONA",
        re.compile(
            _ETIQUETAS_PERSONA + r"\s*[:\-]?\s+(?:(?i:dra?\.|doctora?|sra?\.|se[ñn]ora?)\s+)?"
            # Una etiqueta nunca es el nombre: en «FORMULA MEDICA Paciente: Ana Ruiz», «MEDICA» no
            # puede tomar «Paciente» como nombre: se comería la etiqueta y Ana quedaría expuesta.
            r"(?!" + _ETIQUETAS_PERSONA + r"\b)"
            r"(?P<v>" + _NOMBRE_MAYUS + "|" + _NOMBRE + ")"
        ),
        "v",
    ),
]

# Los marcadores que escribe el modelo pueden llegar con otra capitalización o con espacios.
_MARCADOR = re.compile(
    r"\[\s*(PERSONA|DOCUMENTO|TELEFONO|CORREO|DIRECCION|NACIMIENTO)[_\s-]*(\d+)\s*\]", re.IGNORECASE
)


def _clave(valor: str) -> str:
    return re.sub(r"\s+", " ", valor).strip().casefold()


@dataclass
class Anonimizador:
    """Mapa reversible de UNA consulta: el mismo dato recibe siempre el mismo marcador."""

    _por_marcador: dict[str, str] = field(default_factory=dict)
    _por_valor: dict[tuple[str, str], str] = field(default_factory=dict)
    _cuenta: dict[str, int] = field(default_factory=dict)

    def _marcador(self, tipo: str, valor: str) -> str:
        clave = (tipo, _clave(valor))
        if clave not in self._por_valor:
            self._cuenta[tipo] = self._cuenta.get(tipo, 0) + 1
            marcador = f"[{tipo}_{self._cuenta[tipo]}]"
            self._por_valor[clave] = marcador
            self._por_marcador[marcador] = valor.strip()
        return self._por_valor[clave]

    def enmascarar(self, texto: str) -> str:
        for tipo, patron, grupo in _REGLAS:

            def sustituir(m: re.Match[str], tipo: str = tipo, grupo: str | int = grupo) -> str:
                valor = m.group(grupo)
                if grupo == 0:
                    return self._marcador(tipo, valor)
                inicio, fin = m.span(grupo)
                base = m.start()
                completo = m.group(0)
                marcador = self._marcador(tipo, valor)
                return completo[: inicio - base] + marcador + completo[fin - base :]

            texto = patron.sub(sustituir, texto)
        return texto

    def restaurar(self, texto: str) -> str:
        def volver(m: re.Match[str]) -> str:
            normal = f"[{m.group(1).upper()}_{int(m.group(2))}]"
            return self._por_marcador.get(normal, m.group(0))

        return _MARCADOR.sub(volver, texto)

    def restaurar_json(self, valor: Any) -> Any:
        """Restaura los marcadores en todas las cadenas de una estructura JSON."""
        if isinstance(valor, str):
            return self.restaurar(valor)
        if isinstance(valor, list):
            return [self.restaurar_json(v) for v in valor]
        if isinstance(valor, dict):
            return {k: self.restaurar_json(v) for k, v in valor.items()}
        return valor

    @property
    def hay_datos(self) -> bool:
        return bool(self._por_marcador)


def enmascarar_texto(texto: str) -> str:
    """Enmascara sin conservar el mapa: para lo que se indexa y no hay que restaurar."""
    return Anonimizador().enmascarar(texto)


def evidencias_para_la_nube(evidencias: list, anon: Anonimizador) -> list:
    """Copia de las evidencias SOLO para el prompt: texto y sección enmascarados y nombre de archivo
    neutro. Las originales no se tocan: de ellas salen las citas verificadas."""
    copias = []
    for i, e in enumerate(evidencias, start=1):
        copias.append(
            replace(
                e,
                contenido_texto=anon.enmascarar(e.contenido_texto),
                seccion=anon.enmascarar(e.seccion),
                nombre_archivo=f"documento-{i}",
                vecinos=[
                    replace(
                        v,
                        contenido_texto=anon.enmascarar(v.contenido_texto),
                        seccion=anon.enmascarar(v.seccion),
                    )
                    for v in e.vecinos
                ],
            )
        )
    return copias

"""Anonimización de datos personales antes de enviar texto a un proveedor de IA externo.

Qué hace: sustituye por marcadores (`[PERSONA_1]`, `[DOCUMENTO_1]`, `[TELEFONO_1]`, `[CORREO_1]`,
`[DIRECCION_1]`, `[NACIMIENTO_1]`) los datos que identifican a una persona y que aparecen con una
etiqueta que los delata («Paciente: …», «CC 1.234.567», «Cel. 300 123 4567», «Cra 15 # 93-60»…).
El mismo valor recibe siempre el mismo marcador, y la respuesta del modelo se restaura con el mapa
de la consulta, de modo que el usuario ve los datos reales y las citas siguen siendo literales.

Además, una segunda capa (`app/privacidad/nombres.py`) oculta nombres SIN etiqueta con reglas y
listas de nombres y apellidos frecuentes («…lo atendió Juan Pérez»).

Qué NO hace (y el consentimiento lo dice): es un enmascarado por patrones, no una garantía.
- Un nombre poco común, sin etiqueta, sin parentesco ni firma, no se detecta.
- Se descarta a propósito enmascarar números sueltos: en una licitación, un CUM, un registro INVIMA
  o un NIT no son datos de una persona, y taparlos rompería el análisis.

No usa ningún modelo: es determinista y no llama a ningún servicio.
"""

import re
from dataclasses import dataclass, field, replace
from typing import Any

from app.core.config import get_settings
from app.privacidad import nombres

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
    # Palabras de nombres ya identificados: sirven para reconocerlos cuando vuelven solos.
    _conocidos: set[str] = field(default_factory=set)
    nombres_sueltos: bool = field(default_factory=lambda: get_settings().anonimizar_nombres_sueltos)

    def _marcador(self, tipo: str, valor: str) -> str:
        clave = (tipo, _clave(valor))
        if clave not in self._por_valor:
            self._cuenta[tipo] = self._cuenta.get(tipo, 0) + 1
            marcador = f"[{tipo}_{self._cuenta[tipo]}]"
            self._por_valor[clave] = marcador
            self._por_marcador[marcador] = valor.strip()
        return self._por_valor[clave]

    def aprender(self, textos: list[str]) -> None:
        """Identifica los nombres de varios textos ANTES de enmascararlos: así un nombre que solo
        trae etiqueta en el último también se oculta en el primero."""
        if not self.nombres_sueltos:
            return
        for texto in textos:
            Anonimizador(nombres_sueltos=True, _conocidos=self._conocidos).enmascarar(texto)

    def _ocultar_nombres_sin_etiqueta(self, texto: str) -> str:
        # Primera pasada: aprender; segunda: ocultar, ya sabiendo todos los nombres del texto.
        for inicio, fin in nombres.detectar(texto, self._conocidos):
            self._conocidos |= nombres.palabras_de(texto[inicio:fin])
        partes: list[str] = []
        hasta = 0
        for inicio, fin in nombres.detectar(texto, self._conocidos):
            partes += [texto[hasta:inicio], self._marcador("PERSONA", texto[inicio:fin])]
            hasta = fin
        return "".join([*partes, texto[hasta:]])

    def enmascarar(self, texto: str) -> str:
        for tipo, patron, grupo in _REGLAS:

            def sustituir(m: re.Match[str], tipo: str = tipo, grupo: str | int = grupo) -> str:
                valor = m.group(grupo)
                if grupo == 0:
                    return self._marcador(tipo, valor)
                inicio, fin = m.span(grupo)
                if tipo == "PERSONA":
                    valor = nombres.sin_el_renglon_siguiente(m.string, inicio, fin)
                    fin = inicio + len(valor)
                base = m.start()
                completo = m.group(0)
                marcador = self._marcador(tipo, valor)
                return completo[: inicio - base] + marcador + completo[fin - base :]

            texto = patron.sub(sustituir, texto)
        if self.nombres_sueltos:
            for marcador, valor in self._por_marcador.items():
                if marcador.startswith("[PERSONA_"):
                    self._conocidos |= nombres.palabras_de(valor)
            texto = self._ocultar_nombres_sin_etiqueta(texto)
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


def enmascarar_textos(textos: list[str]) -> list[str]:
    """Como `enmascarar_texto`, para las partes de un mismo documento: lo que se aprende en una vale
    en todas."""
    comun = Anonimizador()
    comun.aprender(textos)
    return [Anonimizador(_conocidos=set(comun._conocidos)).enmascarar(t) for t in textos]


def evidencias_para_la_nube(evidencias: list, anon: Anonimizador) -> list:
    """Copia de las evidencias SOLO para el prompt: texto y sección enmascarados y nombre de archivo
    neutro. Las originales no se tocan: de ellas salen las citas verificadas."""
    anon.aprender(
        [t for e in evidencias for v in [e, *e.vecinos] for t in (v.contenido_texto, v.seccion)]
    )
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

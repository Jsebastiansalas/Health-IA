"""Segmentación en fragmentos de 500–1.000 tokens reales (cl100k_base) con ~15 % de solape (Paso 6).

Estrategia:
1. El contenido se divide en unidades pequeñas: oraciones, encabezados y trozos de tabla (que
   repiten la fila de encabezado). Ninguna unidad supera `max - min - margen` tokens; así, al
   cortar por desborde, el fragmento ya tiene al menos `min` tokens.
2. Un encabezado de sección abre fragmento nuevo, sin solape, si el actual ya alcanzó el mínimo.
3. Al cortar por tamaño, el fragmento siguiente arranca con el ~15 % final del anterior.
4. Un último fragmento demasiado corto se une al anterior si cabe.
"""

import re
from dataclasses import dataclass, replace
from functools import lru_cache

import tiktoken

from app.pipeline import secciones
from app.pipeline.modelos import (
    ConfigFragmentacion,
    FragmentoGenerado,
    MetodoExtraccion,
    PaginaExtraida,
)

_MARGEN = 10  # tokens de holgura por separadores entre unidades
_FIN_ORACION = re.compile(r"(?<=[.;:!?])\s+(?=\S)")
_PARRAFOS = re.compile(r"\n\s*\n")


@lru_cache
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def contar_tokens(texto: str) -> int:
    # disallowed_special=() : un PDF puede contener literalmente "<|endoftext|>".
    return len(_encoding().encode(texto, disallowed_special=()))


@dataclass(frozen=True)
class _Unidad:
    texto: str
    tokens: int
    pagina: int
    seccion: str
    es_tabla: bool = False
    inicio_parrafo: bool = False
    es_encabezado: bool = False
    es_solape: bool = False


class Fragmentador:
    def __init__(self, cfg: ConfigFragmentacion):
        if cfg.max_tokens - cfg.min_tokens <= _MARGEN * 2:
            raise ValueError("max_tokens debe superar holgadamente a min_tokens")
        self.cfg = cfg
        self.tope_unidad = cfg.max_tokens - cfg.min_tokens - _MARGEN
        self.enc = _encoding()

    # ---------- Unidades ----------
    def _trocear_por_tokens(self, texto: str) -> list[str]:
        ids = self.enc.encode(texto, disallowed_special=())
        return [
            self.enc.decode(ids[i : i + self.tope_unidad])
            for i in range(0, len(ids), self.tope_unidad)
        ]

    def _unidades_texto(self, texto: str, pagina: int, seccion: str) -> list[_Unidad]:
        unidades: list[_Unidad] = []
        for i, oracion in enumerate(_FIN_ORACION.split(texto)):
            for j, trozo in enumerate(self._trocear_por_tokens(oracion)):
                unidades.append(
                    _Unidad(
                        texto=trozo,
                        tokens=contar_tokens(trozo),
                        pagina=pagina,
                        seccion=seccion,
                        inicio_parrafo=(i == 0 and j == 0),
                    )
                )
        return unidades

    def _unidades_tabla(self, markdown: str, pagina: int, seccion: str) -> list[_Unidad]:
        lineas = markdown.split("\n")
        cabecera, filas = "\n".join(lineas[:2]), lineas[2:]
        tokens_cabecera = contar_tokens(cabecera)
        unidades: list[_Unidad] = []
        grupo: list[str] = []

        def cerrar() -> None:
            if grupo:
                texto = cabecera + "\n" + "\n".join(grupo)
                unidades.append(_Unidad(texto, contar_tokens(texto), pagina, seccion, True, True))
                grupo.clear()

        for fila in filas:
            n = contar_tokens(fila)
            if tokens_cabecera + n + 1 > self.tope_unidad:
                # Fila gigantesca (celdas con párrafos enteros): se trocea sin cabecera.
                cerrar()
                for trozo in self._trocear_por_tokens(fila):
                    unidades.append(
                        _Unidad(trozo, contar_tokens(trozo), pagina, seccion, True, True)
                    )
                continue
            if tokens_cabecera + contar_tokens("\n".join([*grupo, fila])) + 1 > self.tope_unidad:
                cerrar()
            grupo.append(fila)
        cerrar()
        if not filas:  # tabla de una sola fila
            unidades.append(_Unidad(cabecera, tokens_cabecera, pagina, seccion, True, True))
        return unidades

    def _unidades_parrafo(
        self, parrafo: str, pagina: int, seccion: str
    ) -> tuple[list[_Unidad], str]:
        """Las líneas de un párrafo se unen (los PDF cortan líneas por ancho visual); una línea
        de encabezado parte el párrafo y cambia la sección. Devuelve la sección vigente."""
        unidades: list[_Unidad] = []
        lineas: list[str] = []

        def texto_acumulado() -> str:
            return " ".join(linea.strip() for linea in lineas if linea.strip())

        for linea in parrafo.split("\n"):
            if not secciones.es_encabezado(linea):
                lineas.append(linea)
                continue
            if texto := texto_acumulado():
                unidades += self._unidades_texto(texto, pagina, seccion)
            lineas = []
            seccion = secciones.normalizar_titulo(linea)
            for trozo in self._trocear_por_tokens(seccion):
                unidades.append(
                    _Unidad(
                        trozo,
                        contar_tokens(trozo),
                        pagina,
                        seccion,
                        inicio_parrafo=True,
                        es_encabezado=True,
                    )
                )
        if texto := texto_acumulado():
            unidades += self._unidades_texto(texto, pagina, seccion)
        return unidades, seccion

    def unidades(self, paginas: list[PaginaExtraida]) -> list[_Unidad]:
        seccion = secciones.SIN_SECCION
        unidades: list[_Unidad] = []
        for pagina in paginas:
            for parte in pagina.partes:
                if parte.es_tabla:
                    unidades += self._unidades_tabla(parte.texto, pagina.numero, seccion)
                    continue
                for parrafo in _PARRAFOS.split(parte.texto):
                    nuevas, seccion = self._unidades_parrafo(parrafo, pagina.numero, seccion)
                    unidades += nuevas
        return unidades

    # ---------- Agrupación ----------
    @staticmethod
    def _costo(grupo: list[_Unidad]) -> int:
        return sum(u.tokens + 1 for u in grupo)

    @staticmethod
    def _nuevos(grupo: list[_Unidad]) -> int:
        return sum(u.tokens + 1 for u in grupo if not u.es_solape)

    def _solape(self, grupo: list[_Unidad]) -> list[_Unidad]:
        objetivo = round(self.cfg.overlap_ratio * self._costo(grupo))
        cola: list[_Unidad] = []
        acumulado = 0
        for u in reversed(grupo):
            if acumulado + u.tokens + 1 > objetivo:
                break
            cola.insert(0, replace(u, es_solape=True, es_encabezado=False))
            acumulado += u.tokens + 1
        if not cola and grupo:
            # La última unidad es más larga que el solape: se toman sus últimos tokens.
            ultima = grupo[-1]
            ids = self.enc.encode(ultima.texto, disallowed_special=())[-objetivo:]
            texto = self.enc.decode(ids)
            cola = [
                replace(
                    ultima,
                    texto=texto,
                    tokens=len(ids),
                    es_solape=True,
                    es_encabezado=False,
                    inicio_parrafo=True,
                )
            ]
        return cola

    def agrupar(self, unidades: list[_Unidad]) -> list[list[_Unidad]]:
        grupos: list[list[_Unidad]] = []
        actual: list[_Unidad] = []
        for u in unidades:
            if u.es_encabezado and self._nuevos(actual) >= self.cfg.min_tokens:
                grupos.append(actual)
                actual = []  # una sección nueva arranca limpia, sin solape
            elif self._costo(actual) + u.tokens + 1 > self.cfg.max_tokens:
                grupos.append(actual)
                actual = self._solape(actual)
            actual.append(u)

        nuevos = [u for u in actual if not u.es_solape]
        if nuevos:
            if (
                grupos
                and self._nuevos(nuevos) < self.cfg.min_tokens
                and self._costo(grupos[-1]) + self._costo(nuevos) <= self.cfg.max_tokens
            ):
                grupos[-1] = grupos[-1] + nuevos
            else:
                grupos.append(actual)
        return grupos

    # ---------- Resultado ----------
    @staticmethod
    def _texto(grupo: list[_Unidad]) -> str:
        partes: list[str] = []
        for i, u in enumerate(grupo):
            if i:
                partes.append("\n\n" if u.inicio_parrafo or u.es_tabla else " ")
            partes.append(u.texto)
        return "".join(partes).strip()

    @staticmethod
    def _seccion(grupo: list[_Unidad]) -> str:
        vistas: list[str] = []
        for u in grupo:
            if not u.es_solape and u.seccion not in vistas:
                vistas.append(u.seccion)
        if not vistas:
            vistas = [grupo[0].seccion]
        return " / ".join(vistas)[:255]

    def fragmentar(self, paginas: list[PaginaExtraida]) -> list[FragmentoGenerado]:
        por_numero = {p.numero: p for p in paginas}
        fragmentos: list[FragmentoGenerado] = []
        for orden, grupo in enumerate(self.agrupar(self.unidades(paginas)), start=1):
            texto = self._texto(grupo)
            numeros = sorted({u.pagina for u in grupo})
            fragmentos.append(
                FragmentoGenerado(
                    orden=orden,
                    pagina_inicio=numeros[0],
                    pagina_fin=numeros[-1],
                    seccion=self._seccion(grupo),
                    texto=texto,
                    token_count=contar_tokens(texto),
                    metadata=_metadata([por_numero[n] for n in numeros], grupo),
                )
            )
        return fragmentos


def _metadata(paginas: list[PaginaExtraida], grupo: list[_Unidad]) -> dict:
    metodos = {p.metodo for p in paginas}
    if metodos == {MetodoExtraccion.OCR}:
        metodo = MetodoExtraccion.OCR
    elif MetodoExtraccion.OCR in metodos:
        metodo = MetodoExtraccion.MIXED
    else:
        metodo = MetodoExtraccion.NATIVE
    confianzas = [p.ocr_confidence for p in paginas if p.ocr_confidence is not None]
    return {
        "extraction_method": metodo.value,
        # La más baja de las páginas OCR: es la que determina si hay que mirar el original.
        "ocr_confidence": min(confianzas) if confianzas else None,
        "has_tables": any(u.es_tabla for u in grupo),
        "has_visual_elements": any(p.has_visual_elements for p in paginas),
        "has_signatures_or_stamps": any(p.has_signatures_or_stamps for p in paginas),
    }


def cabecera_contextual(
    codigo_expediente: str, nombre_archivo: str, tipo_documento: str, f: FragmentoGenerado
) -> str:
    """Cabecera que se antepone al texto antes de pedir el embedding (Paso 7)."""
    return (
        f"[Expediente: {codigo_expediente} | Doc: {nombre_archivo} | Tipo: {tipo_documento} | "
        f"Pág: {f.pagina_inicio}-{f.pagina_fin} | Sección: {f.seccion}] {f.texto}"
    )

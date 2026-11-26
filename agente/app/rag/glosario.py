# ruff: noqa: E501
"""Búsqueda de términos del glosario curado en el texto de un documento.

La capa «Qué significan estos términos» de «Explícame este documento» sale de aquí y NO del modelo: se
buscan, en el texto del propio documento, los términos que el glosario conoce y se muestra su explicación
curada. Así lo que se explica es general, revisable una sola vez por un profesional y nunca inventado.
"""

import re
from functools import lru_cache

from app.medicamentos.normalizar import normalizar
from app.rag.glosario_datos import COMUNES, ENTRADAS, GLOSARIO_REVISADO, REVISION

MAX_TERMINOS = 8


@lru_cache(maxsize=1)
def _alias() -> list[tuple[str, re.Pattern[str], int]]:
    """(índice de la entrada, patrón, longitud) de cada alias, el más largo primero."""
    filas = []
    for i, (_nombre, alias, _expl) in enumerate(ENTRADAS):
        for a in alias:
            n = normalizar(a)
            if n:
                filas.append((i, re.compile(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])"), len(n)))
    return sorted(filas, key=lambda f: -f[2])


def terminos_en(textos: list[str], maximo: int = MAX_TERMINOS) -> list[dict]:
    """Los términos del glosario que aparecen en los textos, en orden de aparición y sin repetir.
    Un alias largo («glucosa en ayunas») tapa a uno más corto que lo contiene («glucosa»)."""
    texto = " ".join(normalizar(t) for t in textos)
    ocupado: list[tuple[int, int]] = []
    primera_aparicion: dict[int, int] = {}
    for indice, patron, _largo in _alias():
        for m in patron.finditer(texto):
            if any(m.start() < fin and m.end() > ini for ini, fin in ocupado):
                continue
            ocupado.append((m.start(), m.end()))
            primera_aparicion[indice] = min(primera_aparicion.get(indice, m.start()), m.start())
    orden = sorted(primera_aparicion, key=primera_aparicion.get)
    # Los términos de estructura («Diagnóstico», «Hallazgos») van al final: solo si sobra espacio.
    orden = [i for i in orden if ENTRADAS[i][0] not in COMUNES] + [
        i for i in orden if ENTRADAS[i][0] in COMUNES
    ]
    return [{"termino": ENTRADAS[i][0], "explicacion": ENTRADAS[i][2]} for i in orden[:maximo]]


def estado() -> dict:
    return {"revisado": GLOSARIO_REVISADO, "revision": REVISION, "terminos": len(ENTRADAS)}

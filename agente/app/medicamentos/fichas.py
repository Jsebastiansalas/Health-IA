"""Fichas técnicas oficiales de medicamentos (CIMA, AEMPS de España) para responder por efectos,
contraindicaciones, interacciones y embarazo CON FUENTE.

Solo se cargan las secciones informativas de seguridad; nunca la posología (4.2) ni la sobredosis: el
asistente no indica dosis. Cada sección guarda su enlace al documento original, de modo que toda cita se
puede comprobar. Los medicamentos son los de la fuente (España): el principio activo es el mismo, pero
el nombre comercial y el registro sanitario no son los de Colombia, y así se le dice a la persona.
"""

import re
from collections.abc import Callable
from html import unescape
from html.parser import HTMLParser

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.medicamentos.normalizar import normalizar

BASE = "https://cima.aemps.es/cima/rest"
ORIGEN = "https://cima.aemps.es/cima/dochtml/ft/{nregistro}/FT_{nregistro}.html"
ATRIBUCION = (
    "Fichas técnicas de la AEMPS (CIMA, cima.aemps.es). Se muestran tal cual constan en la fuente."
)

# Seccion de la ficha tecnica -> nombre. Sin 4.2 (posologia) ni 4.9 (sobredosis) a proposito.
SECCIONES = {
    "4.1": "Indicaciones terapéuticas",
    "4.3": "Contraindicaciones",
    "4.4": "Advertencias y precauciones",
    "4.5": "Interacciones",
    "4.6": "Embarazo y lactancia",
    "4.8": "Reacciones adversas",
}
MAX_CARACTERES_SECCION = 12000

_ESPACIOS = re.compile(r"[ \t\r\f\v]+")
_SALTOS = re.compile(r"\n{3,}")


class _Texto(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "li":
            self.partes.append("\n- ")
        elif tag in ("p", "div", "br", "tr", "h1", "h2", "h3", "h4"):
            self.partes.append("\n")
        elif tag in ("td", "th"):
            self.partes.append(" | ")

    def handle_data(self, data: str) -> None:
        self.partes.append(data)


def html_a_texto(html: str) -> str:
    """Texto plano legible de una sección: sin etiquetas ni estilos, con las viñetas y los párrafos."""
    p = _Texto()
    p.feed(html or "")
    texto = unescape("".join(p.partes)).replace("\xa0", " ")
    lineas = [_ESPACIOS.sub(" ", linea).strip() for linea in texto.split("\n")]
    return _SALTOS.sub("\n\n", "\n".join(lineas)).strip()


async def _json(cliente: httpx.AsyncClient, ruta: str, **params) -> dict | list | None:
    r = await cliente.get(f"{BASE}/{ruta}", params=params)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    datos = r.json()
    return None if isinstance(datos, dict) and datos.get("error") else datos


async def cargar_fichas(
    session: AsyncSession,
    cliente: httpx.AsyncClient,
    principios: list[str],
    *,
    por_principio: int = 2,
    avance: Callable[[str], None] = lambda _m: None,
) -> int:
    """Descarga las fichas de hasta `por_principio` medicamentos comercializados por principio activo y
    reemplaza lo que hubiera de cada uno. Devuelve las secciones guardadas."""
    total = 0
    for principio in principios:
        norm = normalizar(principio)
        if not norm:
            continue
        busqueda = await _json(
            cliente, "medicamentos", practiv1=principio, comerc=1, pagesize=por_principio * 3
        )
        encontrados = 0
        for med in (busqueda or {}).get("resultados", []):
            if encontrados >= por_principio:
                break
            nreg = str(med.get("nregistro") or "")
            if not nreg or not any(
                d.get("tipo") == 1 and d.get("secc") for d in med.get("docs", [])
            ):
                continue  # sin ficha técnica segmentada
            filas = []
            for seccion, titulo in SECCIONES.items():
                partes = await _json(
                    cliente, "docSegmentado/contenido/1", nregistro=nreg, seccion=seccion
                )
                for parte in partes or []:
                    texto = html_a_texto(parte.get("contenido", ""))[:MAX_CARACTERES_SECCION]
                    if texto:
                        filas.append(
                            {
                                "fuente": "CIMA",
                                "nregistro": nreg,
                                "medicamento": str(med.get("nombre") or nreg)[:300],
                                "principio_activo": principio.strip()[:200],
                                "principio_norm": norm[:200],
                                "seccion": seccion,
                                "titulo": titulo,
                                "texto": texto,
                                "url_origen": ORIGEN.format(nregistro=nreg),
                            }
                        )
            if not filas:
                continue
            await session.execute(
                text("DELETE FROM med_ficha WHERE fuente = 'CIMA' AND nregistro = :n"), {"n": nreg}
            )
            await session.execute(
                text(
                    "INSERT INTO med_ficha (fuente, nregistro, medicamento, principio_activo, "
                    "principio_norm, seccion, titulo, texto, url_origen) VALUES (:fuente, :nregistro, "
                    ":medicamento, :principio_activo, :principio_norm, :seccion, :titulo, :texto, :url_origen)"
                ),
                filas,
            )
            await session.commit()
            encontrados += 1
            total += len(filas)
            avance(f"{principio}: {med.get('nombre')} ({len(filas)} secciones)")
        if not encontrados:
            avance(f"{principio}: sin ficha técnica en la fuente")
    return total


async def fichas_de(session: AsyncSession, principio: str, limite: int = 12) -> list[dict]:
    """Secciones guardadas del principio activo (o de uno que lo contenga), las más relevantes primero:
    contraindicaciones, advertencias, interacciones, embarazo, reacciones, indicaciones."""
    norm = normalizar(principio)
    if not norm:
        return []
    filas = (
        await session.execute(
            text(
                "SELECT id, nregistro, medicamento, principio_activo, seccion, titulo, texto, url_origen, "
                "cargado_at FROM med_ficha WHERE principio_norm = :n OR principio_norm LIKE :c "
                "ORDER BY nregistro, array_position(ARRAY['4.3','4.4','4.5','4.6','4.8','4.1'], seccion) "
                "LIMIT :l"
            ),
            {"n": norm, "c": f"%{norm}%", "l": limite},
        )
    ).mappings()
    return [dict(f) for f in filas]

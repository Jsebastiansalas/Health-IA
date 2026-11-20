"""Carga de los conjuntos abiertos de INVIMA (datos.gov.co, API Socrata) a la base local.

    python -m app.cli cargar-medicamentos [--fuente VIGENTE --fuente PRECIO ...]

Cada fuente se reemplaza completa en una sola transacción: si algo falla a medias, queda la carga
anterior intacta. Licencia de los datos: CC BY-SA 4.0 (INVIMA); la interfaz la cita.
"""

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass, field

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.medicamentos.normalizar import fecha, limpiar, normalizar, numero

log = logging.getLogger(__name__)

BASE = "https://www.datos.gov.co/resource"
PAGINA = 50_000
LOTE_INSERCION = 4_000


@dataclass(frozen=True)
class Conjunto:
    fuente: str
    dataset_id: str
    nombre: str


CONJUNTOS: dict[str, Conjunto] = {
    c.fuente: c
    for c in (
        Conjunto("VIGENTE", "i7cb-raxc", "Código único de medicamentos vigentes"),
        Conjunto("RENOVACION", "vgr4-gemg", "Código único de medicamentos en trámite de renovación"),
        Conjunto("OTROS", "spzp-dfuc", "Código único de medicamentos en otros estados"),
        Conjunto("VENCIDO", "vwwf-4ftk", "Código único de medicamentos vencidos"),
        Conjunto(
            "PRECIO",
            "nauz-qkjw",
            "Precio máximo de venta de los medicamentos por presentación comercial",
        ),
    )
}


# ---------- Paginación ----------
async def paginas(
    cliente: httpx.AsyncClient, dataset_id: str, orden: str, pagina: int | None = None
) -> AsyncIterator[list[dict]]:
    """Pagina el conjunto con un orden determinista (con `:id` de desempate)."""
    pagina = pagina or PAGINA
    desplazamiento = 0
    token = os.environ.get("SOCRATA_APP_TOKEN")
    cabeceras = {"X-App-Token": token} if token else {}
    while True:
        params = {"$limit": pagina, "$offset": desplazamiento, "$order": f"{orden},:id"}
        filas: list[dict] = []
        for intento in range(5):
            try:
                r = await cliente.get(f"{BASE}/{dataset_id}.json", params=params, headers=cabeceras)
                r.raise_for_status()
                filas = r.json()
                break
            except (httpx.HTTPError, ValueError) as exc:
                if intento == 4:
                    raise
                espera = 2**intento
                log.warning("datos.gov.co %s: %s; reintento en %ss", dataset_id, exc, espera)
                await asyncio.sleep(espera)
        if not filas:
            return
        yield filas
        if len(filas) < pagina:
            return
        desplazamiento += pagina


# ---------- Agrupación de filas por CUM ----------
def _principio(f: dict) -> dict | None:
    nombre = limpiar(f.get("principioactivo"), 200)
    if not nombre:
        return None
    return {
        "nombre": nombre,
        "n": normalizar(nombre),
        "cantidad": limpiar(f.get("cantidad"), 40),
        "unidad": limpiar(f.get("unidadmedida"), 40),
        "referencia": limpiar(f.get("unidadreferencia"), 120),
    }


def _rol(f: dict) -> dict | None:
    nombre = limpiar(f.get("nombrerol"), 200)
    tipo = limpiar(f.get("tiporol"), 60)
    if not nombre and not tipo:
        return None
    return {"tipo": tipo, "nombre": nombre, "modalidad": limpiar(f.get("modalidad"), 80)}


def _clave(f: dict) -> tuple[str, str]:
    return (
        str(f.get("expedientecum") or f.get("expediente") or ""),
        str(f.get("consecutivocum") or ""),
    )


@dataclass
class Grupo:
    base: dict
    principios: list[dict] = field(default_factory=list)
    roles: list[dict] = field(default_factory=list)

    def sumar(self, f: dict) -> None:
        for lista, item in ((self.principios, _principio(f)), (self.roles, _rol(f))):
            if item and item not in lista:
                lista.append(item)


class Agrupador:
    """Junta las filas consecutivas de un mismo CUM (el origen trae una fila por principio activo y
    por rol). Requiere filas ordenadas por CUM; el último grupo se entrega en `cerrar()`."""

    def __init__(self) -> None:
        self._clave: tuple[str, str] | None = None
        self._grupo: Grupo | None = None

    def alimentar(self, filas: Iterable[dict]) -> list[Grupo]:
        listos: list[Grupo] = []
        for f in filas:
            k = _clave(f)
            if self._grupo is None or k != self._clave:
                if self._grupo is not None:
                    listos.append(self._grupo)
                self._clave, self._grupo = k, Grupo(base=f)
            self._grupo.sumar(f)
        return listos

    def cerrar(self) -> list[Grupo]:
        g, self._grupo, self._clave = self._grupo, None, None
        return [g] if g else []


def fila_cum(fuente: str, g: Grupo) -> dict:
    b = g.base
    exp, cons = _clave(b)
    producto = limpiar(b.get("producto"), 400)
    titular = limpiar(b.get("titular"), 300)
    registro = limpiar(b.get("registrosanitario"), 60)
    atc = limpiar(b.get("atc"), 20)
    desc_atc = limpiar(b.get("descripcionatc"), 300)
    forma = limpiar(b.get("formafarmaceutica"), 200)
    via = limpiar(b.get("viaadministracion"), 120)
    nombres = " ".join(p["nombre"] for p in g.principios)
    busqueda = normalizar(
        " ".join(
            x or ""
            for x in (producto, titular, registro, atc, desc_atc, forma, via, nombres, f"{exp} {cons}")
        )
    )
    return {
        "fuente": fuente,
        "expediente_invima": exp[:20],
        "consecutivo": cons[:10],
        "producto": producto,
        "titular": titular,
        "registro_sanitario": registro,
        "estado_registro": limpiar(b.get("estadoregistro"), 60),
        "fecha_expedicion": fecha(b.get("fechaexpedicion")),
        "fecha_vencimiento": fecha(b.get("fechavencimiento")),
        "estado_cum": limpiar(b.get("estadocum"), 40),
        "fecha_activo": fecha(b.get("fechaactivo")),
        "fecha_inactivo": fecha(b.get("fechainactivo")),
        "descripcion_comercial": limpiar(b.get("descripcioncomercial")),
        "cantidad_cum": limpiar(b.get("cantidadcum"), 40),
        "unidad": limpiar(b.get("unidad"), 20),
        "muestra_medica": limpiar(b.get("muestramedica"), 10),
        "atc": atc,
        "descripcion_atc": desc_atc,
        "via_administracion": via,
        "forma_farmaceutica": forma,
        "principios": json.dumps(g.principios, ensure_ascii=False),
        "roles": json.dumps(g.roles, ensure_ascii=False),
        "ium": limpiar(b.get("ium"), 40),
        "producto_n": normalizar(producto),
        "titular_n": normalizar(titular),
        "busqueda": busqueda,
    }


def fila_precio(f: dict) -> dict:
    cum = limpiar(f.get("cum"), 30) or ""
    medicamento = limpiar(f.get("medicamento"))
    mercado = limpiar(f.get("mercado_relevante"), 300)
    return {
        "cum": cum,
        "mercado_relevante": mercado,
        "medicamento": medicamento,
        "cantidad_unidad": limpiar(f.get("cantidad_por_unidad_de_medida"), 40),
        "unidad_medida": limpiar(f.get("unidad_de_medida"), 40),
        "precio_institucional": numero(
            f.get("precio_maximo_de_venta_transaccion_primaria_secundaria_y_final_institucional")
        ),
        "margen_ips": numero(f.get("margen_para_ips")),
        "precio_comercial": numero(
            f.get("precio_maximo_de_venta_transaccion_primaria_y_secundaria_comercial")
        ),
        "precio_final_comercial": numero(
            f.get("precio_maximo_de_venta_transaccion_final_comercial")
        ),
        "circular": limpiar(f.get("circular_cnpmdm"), 120),
        "vigencia_desde": fecha(f.get("fecha_de_inicio_vigencia_precio_maximo_de_venta")),
        "busqueda": normalizar(f"{medicamento or ''} {mercado or ''} {cum}"),
    }


_INSERT_CUM = text(
    """
    INSERT INTO med_cum (fuente, expediente_invima, consecutivo, producto, titular, registro_sanitario,
        estado_registro, fecha_expedicion, fecha_vencimiento, estado_cum, fecha_activo, fecha_inactivo,
        descripcion_comercial, cantidad_cum, unidad, muestra_medica, atc, descripcion_atc,
        via_administracion, forma_farmaceutica, principios, roles, ium, producto_n, titular_n, busqueda)
    VALUES (:fuente, :expediente_invima, :consecutivo, :producto, :titular, :registro_sanitario,
        :estado_registro, :fecha_expedicion, :fecha_vencimiento, :estado_cum, :fecha_activo,
        :fecha_inactivo, :descripcion_comercial, :cantidad_cum, :unidad, :muestra_medica, :atc,
        :descripcion_atc, :via_administracion, :forma_farmaceutica,
        CAST(:principios AS jsonb), CAST(:roles AS jsonb), :ium, :producto_n, :titular_n, :busqueda)
    """
)

_INSERT_PRECIO = text(
    """
    INSERT INTO med_precio (cum, mercado_relevante, medicamento, cantidad_unidad, unidad_medida,
        precio_institucional, margen_ips, precio_comercial, precio_final_comercial, circular,
        vigencia_desde, busqueda)
    VALUES (:cum, :mercado_relevante, :medicamento, :cantidad_unidad, :unidad_medida,
        :precio_institucional, :margen_ips, :precio_comercial, :precio_final_comercial, :circular,
        :vigencia_desde, :busqueda)
    """
)


async def _insertar(session: AsyncSession, sentencia, filas: list[dict]) -> None:
    for i in range(0, len(filas), LOTE_INSERCION):
        await session.execute(sentencia, filas[i : i + LOTE_INSERCION])


async def cargar_fuente(
    session: AsyncSession,
    cliente: httpx.AsyncClient,
    fuente: str,
    avance: Callable[[str], None] = lambda _: None,
) -> int:
    """Reemplaza por completo una fuente. Devuelve cuántas filas quedaron."""
    c = CONJUNTOS[fuente]
    total = 0
    if fuente == "PRECIO":
        await session.execute(text("DELETE FROM med_precio"))
        async for filas in paginas(cliente, c.dataset_id, "cum"):
            lote = [fila_precio(f) for f in filas]
            await _insertar(session, _INSERT_PRECIO, lote)
            total += len(lote)
            avance(f"{fuente}: {total} filas")
    else:
        await session.execute(text("DELETE FROM med_cum WHERE fuente = :f"), {"f": fuente})
        agrupador = Agrupador()
        async for filas in paginas(cliente, c.dataset_id, "expedientecum,consecutivocum"):
            lote = [fila_cum(fuente, g) for g in agrupador.alimentar(filas)]
            await _insertar(session, _INSERT_CUM, lote)
            total += len(lote)
            avance(f"{fuente}: {total} CUM")
        resto = [fila_cum(fuente, g) for g in agrupador.cerrar()]
        await _insertar(session, _INSERT_CUM, resto)
        total += len(resto)
    await session.execute(
        text(
            "INSERT INTO med_carga (fuente, dataset_id, nombre, filas, cargado_at) "
            "VALUES (:f, :d, :n, :t, now()) ON CONFLICT (fuente) DO UPDATE "
            "SET dataset_id = :d, nombre = :n, filas = :t, cargado_at = now()"
        ),
        {"f": fuente, "d": c.dataset_id, "n": c.nombre, "t": total},
    )
    await session.commit()
    return total

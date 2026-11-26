"""Búsqueda estructurada en la base de medicamentos (sin vectores: son datos tabulares).

Los filtros llegan ya interpretados (los extrae el modelo de la pregunta) y aquí se traducen a SQL
parametrizado: el modelo nunca escribe SQL. Los nombres se comparan normalizados (sin tildes ni
mayúsculas) con LIKE sobre índices trigrama; si nada coincide se reintenta con similitud aproximada.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.medicamentos.normalizar import normalizar

FUENTES = ("VIGENTE", "RENOVACION", "OTROS", "VENCIDO")
_CUM = re.compile(r"^\s*(\d{3,9})\s*[-/]\s*(\d{1,3})\s*$")
_ATC = re.compile(r"^[a-z]\d{2}([a-z]{0,2}\d{0,2})?$", re.IGNORECASE)
_NUMERO = re.compile(r"(\d+(?:[.,]\d+)?)\s*([a-zµ%]+(?:/[a-z0-9]+)?)?", re.IGNORECASE)


@dataclass
class Filtros:
    producto: str = ""
    principio_activo: str = ""
    titular: str = ""
    atc: str = ""
    forma: str = ""
    via: str = ""
    concentracion: str = ""
    registro_sanitario: str = ""
    cum: str = ""
    estado: str = ""  # VIGENTE | RENOVACION | OTROS | VENCIDO | "" (todos)
    texto: str = ""

    def vacio(self) -> bool:
        return not any(
            (
                self.producto,
                self.principio_activo,
                self.titular,
                self.atc,
                self.forma,
                self.via,
                self.concentracion,
                self.registro_sanitario,
                self.cum,
                self.texto,
            )
        )

    def como_dict(self) -> dict[str, str]:
        return {k: v for k, v in self.__dict__.items() if v}


@dataclass
class Resultado:
    registros: list[dict[str, Any]] = field(default_factory=list)  # uno por registro sanitario
    total_cum: int = 0
    total_registros: int = 0
    por_fuente: list[dict[str, Any]] = field(default_factory=list)
    titulares_distintos: int = 0
    top_titulares: list[dict[str, Any]] = field(default_factory=list)
    aproximada: bool = False
    precios: list[dict[str, Any]] = field(default_factory=list)


def _tokens(valor: str) -> list[str]:
    return [t for t in normalizar(valor).split() if len(t) >= 2]


def _concentracion(valor: str) -> tuple[str | None, str | None]:
    """«50 mg» -> («50», «mg»). Solo se usa el número como criterio fuerte."""
    m = _NUMERO.search(valor.replace(",", "."))
    if not m:
        return None, None
    return m.group(1), (normalizar(m.group(2)) if m.group(2) else None)


def _condiciones(f: Filtros, aproximada: bool) -> tuple[list[str], dict[str, Any]]:
    cond: list[str] = []
    p: dict[str, Any] = {}

    def like(columna: str, clave: str, valor: str) -> None:
        for i, t in enumerate(_tokens(valor)):
            p[f"{clave}{i}"] = f"%{t}%"
            cond.append(f"{columna} LIKE :{clave}{i}")

    if f.estado in FUENTES:
        cond.append("fuente = :estado")
        p["estado"] = f.estado

    if f.cum:
        m = _CUM.match(f.cum)
        if m:
            cond.append("expediente_invima = :cum_e AND consecutivo = :cum_c")
            p["cum_e"], p["cum_c"] = m.group(1), str(int(m.group(2)))
        elif f.cum.strip().isdigit():
            cond.append("expediente_invima = :cum_e")
            p["cum_e"] = f.cum.strip()

    if f.registro_sanitario:
        crudo = re.sub(r"\s+", "", f.registro_sanitario)
        cond.append("REPLACE(registro_sanitario, ' ', '') ILIKE :registro")
        p["registro"] = f"%{crudo}%"

    if aproximada:
        # Coincidencia aproximada sobre el nombre (errores de escritura, variantes).
        nombre = " ".join(x for x in (f.producto, f.principio_activo) if x)
        if nombre:
            p["aprox"] = normalizar(nombre)
            cond.append(":aprox <% busqueda")
    else:
        like("producto_n", "prod", f.producto)

    if f.principio_activo and not aproximada:
        # El texto indexado ya incluye los principios (filtro rápido por índice); el EXISTS
        # confirma que el nombre es de un principio activo y no del producto o del titular.
        elementos = [f"p->>'n' LIKE :pa{i}" for i in range(len(_tokens(f.principio_activo)))]
        for i, t in enumerate(_tokens(f.principio_activo)):
            p[f"pa{i}"] = f"%{t}%"
            cond.append(f"busqueda LIKE :pa{i}")
        numero, unidad = _concentracion(f.concentracion) if f.concentracion else (None, None)
        if numero is not None:
            p["conc"] = numero
            elementos.append(
                "CASE WHEN p->>'cantidad' ~ '^[0-9]+([.,][0-9]+)?$' "
                "THEN REPLACE(p->>'cantidad', ',', '.')::numeric END = CAST(:conc AS numeric)"
            )
        if unidad:
            p["unidad"] = unidad
            elementos.append("lower(coalesce(p->>'unidad', '')) = :unidad")
        cond.append(
            "EXISTS (SELECT 1 FROM jsonb_array_elements(principios) p WHERE "
            + " AND ".join(elementos)
            + ")"
        )
    elif f.concentracion and not aproximada:
        numero, unidad = _concentracion(f.concentracion)
        if numero is not None:
            p["conc"] = numero
            sub = (
                "CASE WHEN p->>'cantidad' ~ '^[0-9]+([.,][0-9]+)?$' "
                "THEN REPLACE(p->>'cantidad', ',', '.')::numeric END = CAST(:conc AS numeric)"
            )
            if unidad:
                p["unidad"] = unidad
                sub += " AND lower(coalesce(p->>'unidad', '')) = :unidad"
            cond.append(f"EXISTS (SELECT 1 FROM jsonb_array_elements(principios) p WHERE {sub})")

    like("titular_n", "tit", f.titular)
    like("busqueda", "for", f.forma)
    like("busqueda", "via", f.via)
    like("busqueda", "txt", f.texto)

    if f.atc:
        if _ATC.match(f.atc.strip()):
            cond.append("atc LIKE :atc")
            p["atc"] = f.atc.strip().upper() + "%"
        else:
            like("busqueda", "atcd", f.atc)
    return cond, p


_ORDEN = (
    "CASE c.fuente WHEN 'VIGENTE' THEN 0 WHEN 'RENOVACION' THEN 1 WHEN 'OTROS' THEN 2 ELSE 3 END, "
    "c.fecha_vencimiento DESC NULLS LAST, c.producto"
)


async def _consultar(
    session: AsyncSession, f: Filtros, limite: int, aproximada: bool
) -> Resultado:
    cond, p = _condiciones(f, aproximada)
    donde = " AND ".join(cond) if cond else "TRUE"
    if aproximada:
        await session.execute(text("SET LOCAL pg_trgm.word_similarity_threshold = 0.55"))

    por_fuente = (
        await session.execute(
            text(
                "SELECT fuente, count(*) AS cum, count(DISTINCT registro_sanitario) AS registros "
                f"FROM med_cum WHERE {donde} GROUP BY fuente"
            ),
            p,
        )
    ).mappings().all()
    r = Resultado(aproximada=aproximada)
    r.por_fuente = sorted(
        ({"fuente": x["fuente"], "cum": x["cum"], "registros": x["registros"]} for x in por_fuente),
        key=lambda x: FUENTES.index(x["fuente"]),
    )
    r.total_cum = sum(x["cum"] for x in r.por_fuente)
    r.total_registros = sum(x["registros"] for x in r.por_fuente)
    if not r.total_cum:
        return r

    filas = (
        await session.execute(
            text(
                f"""
                WITH m AS (SELECT * FROM med_cum WHERE {donde}),
                g AS (
                    SELECT fuente, registro_sanitario, min(id) AS rep, count(*) AS presentaciones
                    FROM m GROUP BY fuente, registro_sanitario
                )
                SELECT c.*, g.presentaciones
                FROM g JOIN med_cum c ON c.id = g.rep
                ORDER BY {_ORDEN}
                LIMIT :limite
                """
            ),
            {**p, "limite": limite},
        )
    ).mappings().all()
    r.registros = [dict(x) for x in filas]

    tit = (
        await session.execute(
            text(
                "SELECT titular, count(DISTINCT registro_sanitario) AS registros "
                f"FROM med_cum WHERE {donde} AND titular IS NOT NULL "
                "GROUP BY titular ORDER BY registros DESC, titular LIMIT 8"
            ),
            p,
        )
    ).mappings().all()
    r.top_titulares = [dict(x) for x in tit]
    r.titulares_distintos = (
        await session.execute(
            text(f"SELECT count(DISTINCT titular) FROM med_cum WHERE {donde}"), p
        )
    ).scalar_one()
    return r


async def buscar(session: AsyncSession, f: Filtros, limite: int = 8) -> Resultado:
    """Busca exacta (por palabras) y, si no hay nada, aproximada por similitud de trigramas."""
    r = await _consultar(session, f, limite, aproximada=False)
    if not r.total_cum and (f.producto or f.principio_activo):
        r = await _consultar(session, f, limite, aproximada=True)
    return r


async def buscar_precios(
    session: AsyncSession, f: Filtros, registros: list[dict[str, Any]], limite: int = 10
) -> list[dict[str, Any]]:
    """Precios regulados de las presentaciones encontradas; si no hay por CUM, por nombre."""
    cums = [f"{x['expediente_invima']}-{x['consecutivo']}" for x in registros]
    if cums:
        filas = (
            await session.execute(
                text(
                    "SELECT * FROM med_precio WHERE cum = ANY(:cums) "
                    "ORDER BY vigencia_desde DESC NULLS LAST, cum LIMIT :limite"
                ),
                {"cums": cums, "limite": limite},
            )
        ).mappings().all()
        if filas:
            return [dict(x) for x in filas]
    tokens = _tokens(" ".join(x for x in (f.producto, f.principio_activo) if x))
    if not tokens:
        return []
    cond = " AND ".join(f"busqueda LIKE :t{i}" for i in range(len(tokens)))
    params: dict[str, Any] = {f"t{i}": f"%{t}%" for i, t in enumerate(tokens)}
    filas = (
        await session.execute(
            text(
                f"SELECT * FROM med_precio WHERE {cond} "
                "ORDER BY vigencia_desde DESC NULLS LAST, cum LIMIT :limite"
            ),
            {**params, "limite": limite},
        )
    ).mappings().all()
    return [dict(x) for x in filas]


async def fuentes_cargadas(session: AsyncSession) -> list[dict[str, Any]]:
    filas = (
        await session.execute(
            text("SELECT fuente, dataset_id, nombre, filas, cargado_at FROM med_carga ORDER BY fuente")
        )
    ).mappings().all()
    return [dict(x) for x in filas]

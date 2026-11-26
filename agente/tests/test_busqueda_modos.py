"""hnsw.iterative_scan: el modo por defecto debe ser estricto y el valor está acotado (se interpola
en el SQL de `SET LOCAL`, que no admite parámetros)."""

import uuid

import pytest

from app.core.config import Settings
from app.rag.busqueda import busqueda_hibrida


class SesionEspia:
    def __init__(self):
        self.sentencias: list[str] = []

    async def execute(self, sentencia, parametros=None):
        self.sentencias.append(str(sentencia))
        return []  # sin filas


async def _buscar(**kw):
    s = SesionEspia()
    await busqueda_hibrida(
        s,  # type: ignore[arg-type]
        tenant_id=uuid.uuid4(),
        expediente_id=uuid.uuid4(),
        modelo="gemini-embedding-001",
        vector=[0.1] * 1536,
        texto="garantía",
        **kw,
    )
    return s.sentencias


async def test_por_defecto_el_orden_es_estricto():
    sentencias = await _buscar()
    assert "SET LOCAL hnsw.iterative_scan = 'strict_order'" in sentencias[0]
    assert "relaxed_order" not in " ".join(sentencias)


async def test_relaxed_order_solo_si_se_pide_expresamente():
    assert "relaxed_order" in (await _buscar(iterative="relaxed_order"))[0]


@pytest.mark.parametrize("malo", ["off; DROP TABLE fragmentos", "RELAXED_ORDER", "", "' OR '1'='1"])
async def test_valores_no_permitidos_se_rechazan_antes_de_tocar_la_base(malo):
    s = SesionEspia()
    with pytest.raises(ValueError, match="no soportado"):
        await busqueda_hibrida(
            s,  # type: ignore[arg-type]
            tenant_id=uuid.uuid4(),
            expediente_id=uuid.uuid4(),
            modelo="m",
            vector=[0.0] * 1536,
            texto="x",
            iterative=malo,
        )
    assert s.sentencias == []


def test_la_configuracion_por_defecto_es_estricta():
    assert Settings(jwt_secret="x" * 40).rag_hnsw_iterative == "strict_order"

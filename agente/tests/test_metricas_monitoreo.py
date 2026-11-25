"""Las alertas y el panel solo nombran métricas que de verdad existen.

Una alerta sobre un nombre mal escrito no falla: simplemente no suena nunca.
"""

import re
from pathlib import Path

from app.core.metricas import REGISTRO

RAIZ = Path(__file__).resolve().parents[2]
USOS = [RAIZ / "infra/monitoreo/alertas.yml", RAIZ / "infra/monitoreo/grafana/paneles/medtender.json"]
SUFIJOS = ("", "_total", "_bucket", "_count", "_sum")


def _del_agente() -> set[str]:
    return {familia.name + s for familia in REGISTRO.collect() for s in SUFIJOS}


def _de_los_respaldos() -> set[str]:
    texto = (RAIZ / "infra/backup/estado.sh").read_text(encoding="utf-8")
    return set(re.findall(r"medtender_[a-z0-9_]+", texto))


def _de_la_api() -> set[str]:
    fuentes = (RAIZ / "api-java/src/main/java").rglob("*.java")
    texto = "".join(f.read_text(encoding="utf-8") for f in fuentes)
    return set(re.findall(r'counter\("(medtender_[a-z0-9_]+)"', texto))


def test_cada_metrica_que_se_vigila_existe():
    usadas = set()
    for archivo in USOS:
        usadas |= set(re.findall(r"\bmedtender_[a-z0-9_]+", archivo.read_text(encoding="utf-8")))
    assert len(usadas) > 15  # si el patrón dejara de encontrar nombres, la prueba no probaría nada
    existentes = _del_agente() | _de_los_respaldos() | _de_la_api()
    assert sorted(usadas - existentes) == []

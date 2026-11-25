"""El registro de cambios sale de los mensajes de commit («tipo: emoji mensaje»)."""

import importlib.util
from pathlib import Path

_RUTA = Path(__file__).resolve().parents[2] / "infra/scripts/changelog.py"
_spec = importlib.util.spec_from_file_location("changelog", _RUTA)
changelog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(changelog)


def test_agrupa_por_tipo_quita_el_emoji_y_omite_lo_interno():
    texto = changelog.seccion(
        "v1.2.0",
        "2026-11-25",
        [
            "feat: ✨ sprint 9 - algo nuevo",
            "fix: 🐛 la API ya no cae",
            "perf: ⚡ portada liviana",
            "docs: 📝 guía",
            "test: ✅ pruebas",
            "Merge branch 'x'",
            "mensaje sin formato",
        ],
    )
    assert texto == (
        "## v1.2.0 (2026-11-25)\n\n"
        "### Novedades\n- sprint 9 - algo nuevo\n\n"
        "### Correcciones\n- la API ya no cae\n\n"
        "### Rendimiento\n- portada liviana\n\n"
        "### Documentación\n- guía\n"
    )


def test_una_seccion_sin_nada_que_contar_no_aparece():
    assert changelog.seccion("v1", "2026-01-01", ["test: ✅ x"]) == ""


def test_siguiente_version():
    assert changelog.siguiente("v0.42.1", ["fix: 🐛 a"]) == "v0.42.2"
    assert changelog.siguiente("v0.42.1", ["fix: 🐛 a", "feat: ✨ b"]) == "v0.43.0"
    assert changelog.siguiente(None, ["feat: ✨ b"]) == "v0.1.0"

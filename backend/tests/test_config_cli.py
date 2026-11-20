"""Validación de la configuración de producción y CLI administrativa."""

import psycopg
import pytest

from app import cli
from app.core.config import Settings
from app.main import validar_configuracion

SEGURO = dict(
    entorno="produccion",
    internal_token="Xk9mQ2vL7nR4tB8wZ3pY6cF1hJ5dS0gA",
    database_url="postgresql+asyncpg://medtender:Cl4ve-L4rg4-Y-Unica@postgres:5432/medtender",
    cola_backend="arq",
    gemini_api_key="k",
    metrics_token="t",
)


def ajustes(**cambios) -> Settings:
    return Settings(**{**SEGURO, **cambios})


def test_configuracion_segura_no_tiene_problemas():
    assert ajustes().problemas_produccion() == ([], [])


@pytest.mark.parametrize(
    ("cambio", "texto"),
    [
        ({"internal_token": ""}, "INTERNAL_TOKEN"),
        ({"internal_token": "corto"}, "INTERNAL_TOKEN"),
        ({"internal_token": "a" * 40}, "INTERNAL_TOKEN"),
        (
            {"database_url": "postgresql+asyncpg://medtender:medtender@postgres/medtender"},
            "DATABASE_URL",
        ),
        ({"cola_backend": "ninguna"}, "COLA_BACKEND"),
    ],
)
def test_problemas_fatales(cambio, texto):
    fatales, _ = ajustes(**cambio).problemas_produccion()
    assert any(texto in f for f in fatales)


def test_advertencias_no_bloquean():
    fatales, avisos = ajustes(
        gemini_api_key="",
        openai_api_key="",  # el entorno de pruebas define una key falsa
        metrics_token="",
    ).problemas_produccion()
    assert fatales == []
    texto = " ".join(avisos)
    for esperado in ("API key", "METRICS_TOKEN"):
        assert esperado in texto


def test_arranque_en_produccion_con_configuracion_insegura_falla(monkeypatch):
    from app.core import config

    inseguro = ajustes(internal_token="")
    monkeypatch.setattr("app.main.get_settings", lambda: inseguro)
    with pytest.raises(RuntimeError, match="INTERNAL_TOKEN"):
        validar_configuracion()
    # En desarrollo la misma configuración se tolera.
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(**{**SEGURO, "entorno": "desarrollo", "internal_token": ""}),
    )
    validar_configuracion()
    assert config.get_settings().entorno == "desarrollo"


# ---------- CLI ----------
def _tenants(postgres_url) -> list[tuple]:
    with psycopg.connect(postgres_url) as conn:
        return conn.execute(
            "SELECT t.nombre, t.nit, t.politica_borrado, u.email, u.rol_global, u.activo "
            "FROM tenants t JOIN usuarios u ON u.tenant_id = t.id ORDER BY t.nit"
        ).fetchall()


def test_cli_crea_tenant_y_administrador(postgres_url, monkeypatch, capsys):
    monkeypatch.setenv("MEDTENDER_ADMIN_PASSWORD", "ClaveInicial-2027")
    code = cli.main(
        [
            "crear-tenant",
            "--nombre",
            "Hospital del Valle",
            "--nit",
            "900555",
            "--email",
            "Admin@Valle.co",
            "--politica-borrado",
            "DIFERIDO_1H",
        ]
    )
    assert code == 0
    assert _tenants(postgres_url) == [
        ("Hospital del Valle", "900555", "DIFERIDO_1H", "admin@valle.co", "ADMIN_TENANT", True)
    ]
    assert "ClaveInicial" not in capsys.readouterr().out  # la contraseña nunca se imprime
    with psycopg.connect(postgres_url) as conn:
        (hash_,) = conn.execute("SELECT password_hash FROM usuarios").fetchone()
    assert hash_.startswith("$2") and "ClaveInicial" not in hash_


def test_cli_rechaza_duplicados_y_contrasenas_cortas(postgres_url, monkeypatch, capsys):
    monkeypatch.setenv("MEDTENDER_ADMIN_PASSWORD", "ClaveInicial-2027")
    args = ["crear-tenant", "--nombre", "H", "--nit", "1", "--email", "a@h.co"]
    assert cli.main(args) == 0
    assert cli.main(args) == 1
    assert "ya están registrados" in capsys.readouterr().err
    monkeypatch.setenv("MEDTENDER_ADMIN_PASSWORD", "corta")
    assert cli.main(["crear-tenant", "--nombre", "H2", "--nit", "2", "--email", "b@h.co"]) == 1
    assert len(_tenants(postgres_url)) == 1


def test_cli_rechaza_correos_que_el_login_no_aceptaria(postgres_url, monkeypatch, capsys):
    monkeypatch.setenv("MEDTENDER_ADMIN_PASSWORD", "ClaveInicial-2027")
    for malo in ("admin@prod.test", "sin-arroba", "a@localhost"):
        args = ["crear-tenant", "--nombre", "H", "--nit", "9", "--email", malo]
        assert cli.main(args) == 1, malo
    assert "correo inválido" in capsys.readouterr().err
    assert _tenants(postgres_url) == []  # no se creó nada


def test_cli_verificar_config(capsys, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.get_settings(), "entorno", "desarrollo")
    assert cli.main(["verificar-config"]) == 0
    assert "Entorno: desarrollo" in capsys.readouterr().out

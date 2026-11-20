"""Operaciones administrativas desde la línea de comandos.

    python -m app.cli verificar-config
    python -m app.cli crear-tenant --nombre "Hospital X" --nit 900123 --email admin@hospital.co

Sirve para dar de alta la primera organización en producción sin dejar abierto el registro
público (ALLOW_TENANT_SIGNUP=false). La contraseña se lee de MEDTENDER_ADMIN_PASSWORD o se pide
por teclado; nunca se pasa como argumento (quedaría en el historial del shell).
"""

import argparse
import asyncio
import getpass
import os
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker
from app.core.enums import PoliticaBorrado, RolGlobal
from app.core.security import hash_password
from app.models import Tenant, Usuario


def verificar_config() -> int:
    s = get_settings()
    fatales, avisos = s.problemas_produccion()
    print(f"Entorno: {s.entorno}")
    for f in fatales:
        print(f"  [ERROR] {f}")
    for a in avisos:
        print(f"  [AVISO] {a}")
    if not fatales and not avisos:
        print("  Configuración correcta.")
    return 1 if fatales and s.entorno == "produccion" else 0


async def _crear_tenant(
    nombre: str, nit: str, email: str, nombre_admin: str, password: str, politica: str
) -> int:
    try:
        async with get_sessionmaker()() as session:
            tenant = Tenant(nombre=nombre, nit=nit, politica_borrado=politica)
            session.add(tenant)
            await session.flush()
            session.add(
                Usuario(
                    tenant_id=tenant.id,
                    email=email.lower(),
                    password_hash=hash_password(password),
                    nombre_completo=nombre_admin,
                    rol_global=RolGlobal.ADMIN_TENANT,
                    activo=True,
                )
            )
            await session.commit()
    except IntegrityError:
        print("Error: ese NIT o ese correo ya están registrados.", file=sys.stderr)
        return 1
    finally:
        await get_engine().dispose()
    print(f"Organización «{nombre}» creada con administrador {email.lower()}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="comando", required=True)
    sub.add_parser("verificar-config", help="Revisa la configuración de producción")
    c = sub.add_parser("crear-tenant", help="Crea una organización y su administrador")
    c.add_argument("--nombre", required=True)
    c.add_argument("--nit", required=True)
    c.add_argument("--email", required=True)
    c.add_argument("--nombre-admin", default="Administrador")
    c.add_argument(
        "--politica-borrado",
        choices=[e.value for e in PoliticaBorrado],
        default=PoliticaBorrado.INMEDIATO.value,
    )
    args = p.parse_args(argv)

    if args.comando == "verificar-config":
        return verificar_config()

    # Mismo validador que usa el login: un correo que la API rechazaría dejaría un
    # administrador que nunca podría ingresar.
    try:
        args.email = TypeAdapter(EmailStr).validate_python(args.email)
    except ValidationError as exc:
        motivo = str(exc.errors()[0]["msg"]).removeprefix("value is not a valid email address: ")
        print(f"Error: correo inválido ({motivo})", file=sys.stderr)
        return 1

    password = os.environ.get("MEDTENDER_ADMIN_PASSWORD") or getpass.getpass("Contraseña: ")
    if len(password) < 10 or len(password.encode()) > 72:
        print("Error: la contraseña debe tener entre 10 caracteres y 72 bytes.", file=sys.stderr)
        return 1
    return asyncio.run(
        _crear_tenant(
            args.nombre, args.nit, args.email, args.nombre_admin, password, args.politica_borrado
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

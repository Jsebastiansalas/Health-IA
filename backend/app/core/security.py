import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Literal

import bcrypt
import jwt

from app.core.config import get_settings

TokenType = Literal["access", "refresh"]


class TokenInvalido(Exception):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


# bcrypt consume un núcleo entero durante ~250 ms. Ejecutarlo en el bucle de eventos congela a
# todos los demás usuarios; en el pool por defecto de asyncio, 30 logins simultáneos lanzarían
# 30 hilos disputándose la CPU. Un ejecutor propio con tantos hilos como núcleos acota el
# trabajo y hace esperar en cola al resto (sin ocupar conexiones de base de datos).
_EJECUTOR_HASH = ThreadPoolExecutor(
    max_workers=max(2, os.cpu_count() or 2), thread_name_prefix="bcrypt"
)


async def hash_password_async(password: str) -> str:
    return await asyncio.get_running_loop().run_in_executor(_EJECUTOR_HASH, hash_password, password)


async def verify_password_async(password: str, password_hash: str) -> bool:
    return await asyncio.get_running_loop().run_in_executor(
        _EJECUTOR_HASH, verify_password, password, password_hash
    )


def create_token(
    usuario_id: uuid.UUID, tenant_id: uuid.UUID, rol: str, token_type: TokenType
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    ttl = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    payload = {
        "sub": str(usuario_id),
        "tenant_id": str(tenant_id),
        "rol": rol,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: TokenType) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "tenant_id", "type", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenInvalido(str(exc)) from exc
    if payload.get("type") != expected_type:
        raise TokenInvalido("Tipo de token incorrecto")
    return payload

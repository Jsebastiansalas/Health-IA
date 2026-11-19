"""Límites de peticiones (ventana fija) sobre Redis, con una versión en memoria para pruebas.

Si Redis falla, las peticiones se permiten (fail-open) y se registra el fallo: es preferible no
tumbar el servicio por un problema del limitador, y el resto de defensas (bcrypt, permisos)
siguen activas.
"""

import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import redis.asyncio as aioredis
from fastapi import HTTPException, status

from app.core import contexto
from app.core.config import get_settings
from app.core.metricas import LIMITE_FALLOS, LIMITE_RECHAZOS

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResultadoLimite:
    permitido: bool
    cuenta: int
    reintentar_en_s: int


class Almacen(Protocol):
    async def golpear(self, clave: str, ventana_s: int) -> tuple[int, int]:
        """Suma 1 a la clave y devuelve (cuenta, segundos que faltan para que expire)."""

    async def contar(self, clave: str) -> tuple[int, int]:
        """(cuenta, segundos restantes) sin modificar."""

    async def reiniciar(self) -> None: ...


class AlmacenMemoria:
    def __init__(self) -> None:
        self._datos: dict[str, tuple[int, float]] = {}

    def _vigente(self, clave: str) -> tuple[int, float] | None:
        entrada = self._datos.get(clave)
        if entrada and entrada[1] <= time.monotonic():
            del self._datos[clave]
            return None
        return entrada

    async def golpear(self, clave: str, ventana_s: int) -> tuple[int, int]:
        entrada = self._vigente(clave)
        cuenta, expira = (
            (entrada[0] + 1, entrada[1]) if entrada else (1, time.monotonic() + ventana_s)
        )
        self._datos[clave] = (cuenta, expira)
        return cuenta, max(1, int(expira - time.monotonic()))

    async def contar(self, clave: str) -> tuple[int, int]:
        entrada = self._vigente(clave)
        return (entrada[0], max(1, int(entrada[1] - time.monotonic()))) if entrada else (0, 0)

    async def reiniciar(self) -> None:
        self._datos.clear()


class AlmacenRedis:
    def __init__(self, url: str) -> None:
        self._r = aioredis.from_url(url, socket_timeout=1.0, socket_connect_timeout=1.0)

    async def golpear(self, clave: str, ventana_s: int) -> tuple[int, int]:
        # SET NX EX + INCR + TTL en una transacción: la clave siempre nace con expiración,
        # así un corte entre comandos no deja un contador eterno.
        pipe = self._r.pipeline(transaction=True)
        pipe.set(clave, 0, ex=ventana_s, nx=True)
        pipe.incr(clave)
        pipe.ttl(clave)
        _, cuenta, ttl = await pipe.execute()
        return int(cuenta), max(1, int(ttl))

    async def contar(self, clave: str) -> tuple[int, int]:
        pipe = self._r.pipeline(transaction=False)
        pipe.get(clave)
        pipe.ttl(clave)
        valor, ttl = await pipe.execute()
        return (int(valor), max(1, int(ttl))) if valor is not None else (0, 0)

    async def reiniciar(self) -> None:
        async for k in self._r.scan_iter("rl:*"):
            await self._r.delete(k)

    async def cerrar(self) -> None:
        await self._r.aclose()


@lru_cache
def get_almacen() -> Almacen:
    s = get_settings()
    return AlmacenMemoria() if s.rate_limit_backend == "memoria" else AlmacenRedis(s.redis_url)


def _clave(regla: str, identidad: str, ventana_s: int) -> str:
    # El contador de cada regla se reinicia solo con el TTL; no hace falta numerar ventanas.
    return f"rl:{regla}:{ventana_s}:{identidad}"


async def golpear(regla: str, identidad: str, limite: int, ventana_s: int) -> ResultadoLimite:
    """Registra una solicitud y dice si cabe dentro del límite."""
    if not get_settings().rate_limit_habilitado:
        return ResultadoLimite(True, 0, 0)
    try:
        cuenta, restante = await get_almacen().golpear(
            _clave(regla, identidad, ventana_s), ventana_s
        )
    except Exception:
        LIMITE_FALLOS.inc()
        log.warning("Almacén de límites no disponible; se permite la solicitud", exc_info=True)
        return ResultadoLimite(True, 0, 0)
    return ResultadoLimite(cuenta <= limite, cuenta, restante)


async def excedido(regla: str, identidad: str, limite: int, ventana_s: int) -> ResultadoLimite:
    """¿Ya se alcanzó el límite? No suma. Sirve para bloquear tras N fallos."""
    if not get_settings().rate_limit_habilitado:
        return ResultadoLimite(True, 0, 0)
    try:
        cuenta, restante = await get_almacen().contar(_clave(regla, identidad, ventana_s))
    except Exception:
        LIMITE_FALLOS.inc()
        return ResultadoLimite(True, 0, 0)
    return ResultadoLimite(cuenta < limite, cuenta, restante)


def rechazar(regla: str, reintentar_en_s: int) -> HTTPException:
    LIMITE_RECHAZOS.labels(regla).inc()
    log.warning(
        "Límite excedido regla=%s ip=%s",
        regla,
        contexto.ip_cliente.get(),
        extra={"regla": regla},
    )
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        f"Demasiadas solicitudes. Intente de nuevo en {reintentar_en_s} s.",
        headers={"Retry-After": str(reintentar_en_s)},
    )


async def exigir(regla: str, identidad: str, limite: int, ventana_s: int) -> None:
    r = await golpear(regla, identidad, limite, ventana_s)
    if not r.permitido:
        raise rechazar(regla, r.reintentar_en_s)

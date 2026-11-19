"""Endpoints operativos: salud y métricas. No forman parte de la API pública versionada."""

import hmac
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.metricas import REGISTRO, actualizar_medidores

router = APIRouter(tags=["sistema"])


@router.get("/health")
async def health() -> JSONResponse:
    """Sonda de vida: verifica que PostgreSQL responde."""
    try:
        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "degradado", "db": "error"}, status_code=503)
    return JSONResponse({"status": "ok", "db": "ok"})


@router.get("/metrics", include_in_schema=False)
async def metricas(authorization: Annotated[str | None, Header()] = None) -> Response:
    s = get_settings()
    if s.metrics_token:
        esperado = f"Bearer {s.metrics_token}"
        if not hmac.compare_digest((authorization or "").encode(), esperado.encode()):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de métricas inválido")
    elif s.entorno == "produccion":
        # Sin token en producción las métricas no se publican.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontrado")
    async with get_sessionmaker()() as session:
        await actualizar_medidores(session)
    return Response(generate_latest(REGISTRO), media_type=CONTENT_TYPE_LATEST)

"""Qué proveedor de IA recibe de verdad los datos.

La API Java lo consulta para mostrar y exigir el consentimiento que corresponde. La respuesta sale
de la configuración con la que este proceso llama a la IA, así que el texto que acepta la persona no
puede contradecir lo que se hace con sus datos.
"""

from fastapi import APIRouter, Depends

from app.api.interno import exigir_token
from app.core.config import get_settings

router = APIRouter(prefix="/internal/v1", tags=["interno"], dependencies=[Depends(exigir_token)])


@router.get("/ia")
async def proveedor_activo() -> dict[str, str]:
    s = get_settings()
    # Sin clave, a Claude no se le puede enviar nada: no se anuncia.
    respaldo = s.llm_respaldo_proveedor if s.anthropic_api_key else ""
    return {"proveedor": s.ia_proveedor, "respaldo": respaldo}

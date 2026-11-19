"""Modelo generativo para el Paso 14 (respuesta fundamentada en JSON estructurado).

Los modelos de Gemini pueden devolver 503 por alta demanda. Si el modelo principal está
saturado (429/5xx/timeout tras sus reintentos), se intenta con los de respaldo en orden.
Un error de la petición (4xx distinto de 429) no cambia de modelo: fallaría igual.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.ia.embeddings import ErrorEmbeddings, post_con_reintentos

log = logging.getLogger(__name__)


class ErrorLLM(Exception):
    pass


@dataclass(frozen=True)
class RespuestaLLM:
    datos: dict
    modelo: str  # el modelo que efectivamente respondió


class ProveedorLLM(Protocol):
    async def generar_json(self, sistema: str, prompt: str, esquema: dict) -> RespuestaLLM: ...


def _es_saturacion(mensaje: str) -> bool:
    return mensaje.startswith(("HTTP 429", "HTTP 5", "Proveedor inaccesible"))


@dataclass
class GeminiLLM:
    modelos: list[str]
    api_key: str
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    temperatura: float = 0.1
    timeout_s: float = 60.0
    reintentos: int = 2

    enfriamiento_s: float = 300.0
    _saturado_hasta: dict[str, float] = field(default_factory=dict)

    def _disponibles(self) -> list[str]:
        """Modelos saturados recientemente van al final, para no esperar sus reintentos en
        cada consulta. Si todos lo están, se prueban igual."""
        ahora = time.monotonic()
        libres = [m for m in self.modelos if self._saturado_hasta.get(m, 0) <= ahora]
        return libres + [m for m in self.modelos if m not in libres]

    async def generar_json(self, sistema: str, prompt: str, esquema: dict) -> RespuestaLLM:
        if not self.api_key:
            raise ErrorLLM("GEMINI_API_KEY no configurada")
        ultimo: ErrorLLM | None = None
        for modelo in self._disponibles():
            try:
                datos = await self._generar(modelo, sistema, prompt, esquema)
                self._saturado_hasta.pop(modelo, None)
                return RespuestaLLM(datos, modelo)
            except ErrorLLM as exc:
                if not _es_saturacion(str(exc)):
                    raise
                self._saturado_hasta[modelo] = time.monotonic() + self.enfriamiento_s
                log.warning(
                    "LLM %s saturado; se usa respaldo por %.0fs", modelo, self.enfriamiento_s
                )
                ultimo = exc
        raise ultimo or ErrorLLM("Sin modelos configurados")

    async def _generar(self, modelo: str, sistema: str, prompt: str, esquema: dict) -> dict:
        cuerpo = {
            "systemInstruction": {"parts": [{"text": sistema}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.temperatura,
                "responseMimeType": "application/json",
                "responseSchema": esquema,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as cliente:
                datos = await post_con_reintentos(
                    cliente,
                    f"{self.base_url}/models/{modelo}:generateContent",
                    cuerpo,
                    {"x-goog-api-key": self.api_key},
                    self.reintentos,
                )
        except ErrorEmbeddings as exc:
            raise ErrorLLM(str(exc)) from exc

        candidatos = datos.get("candidates") or []
        if not candidatos:
            bloqueo = datos.get("promptFeedback", {}).get("blockReason")
            raise ErrorLLM(f"El modelo no devolvió respuesta (bloqueo: {bloqueo})")
        partes = candidatos[0].get("content", {}).get("parts", [])
        texto = "".join(p.get("text", "") for p in partes if not p.get("thought"))
        try:
            return json.loads(texto)
        except json.JSONDecodeError as exc:
            raise ErrorLLM(f"Respuesta no es JSON válido: {texto[:200]!r}") from exc


_llm: ProveedorLLM | None = None


def get_llm() -> ProveedorLLM:
    global _llm
    if _llm is None:
        s = get_settings()
        modelos = [s.llm_model, *[m for m in s.llm_modelos_respaldo if m != s.llm_model]]
        _llm = GeminiLLM(
            modelos=modelos,
            api_key=s.gemini_api_key,
            base_url=s.gemini_base_url,
            temperatura=s.llm_temperatura,
            timeout_s=s.llm_timeout_s,
        )
    return _llm

"""Modelo generativo (Paso 14: respuesta fundamentada en JSON estructurado).

Proveedores, todos con la misma interfaz `ProveedorLLM`:
- `GeminiLLM`: API de Google AI Studio con clave. Solo para desarrollo (ver `ia_proveedor`).
- `VertexLLM`: el mismo Gemini en Google Cloud, con cuenta de servicio y sin entrenamiento.
- `ClaudeLLM`: Claude de Anthropic con el SDK oficial, como segundo proveedor.

`LLMConRespaldo` los encadena: si el principal falla, responde el siguiente; un cortacircuitos
deja de insistir sobre un proveedor caído y el control de costo suma lo gastado y aplica el tope
diario. Las garantías deterministas (citas, cifras, posología, límites clínicos) se aplican
después, sobre la respuesta, así que valen igual con cualquier proveedor.

Dentro de Gemini, los modelos pueden devolver 503 por alta demanda: si el modelo principal está
saturado (429/5xx/timeout tras sus reintentos), se intenta con los de respaldo en orden. Un error
de la petición (4xx distinto de 429) no cambia de modelo: fallaría igual.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol

import anthropic
import httpx

from app.core.config import get_settings
from app.core.metricas import IA_CIRCUITO_ABIERTO, IA_RESPALDOS, IA_TOPE_DIARIO
from app.ia.costo import ControlDeCosto, TopeDiarioAlcanzado, Uso
from app.ia.embeddings import ErrorEmbeddings, post_con_reintentos
from app.ia.google_auth import CredencialGoogle, ErrorCredencial, credencial_para, vertex_url

log = logging.getLogger(__name__)


class ErrorLLM(Exception):
    pass


class ErrorTopeDiario(ErrorLLM):
    pass


@dataclass(frozen=True)
class RespuestaLLM:
    datos: dict
    modelo: str  # el modelo que efectivamente respondió
    proveedor: str = ""
    uso: Uso | None = None


class ProveedorLLM(Protocol):
    async def generar_json(self, sistema: str, prompt: str, esquema: dict) -> RespuestaLLM: ...


def _es_saturacion(mensaje: str) -> bool:
    return mensaje.startswith(("HTTP 429", "HTTP 5", "Proveedor inaccesible"))


def _no_disponible(mensaje: str) -> bool:
    """Fallos del proveedor (no de la petición): cuentan para el cortacircuitos."""
    return _es_saturacion(mensaje) or mensaje.startswith(("HTTP 401", "HTTP 403", "Credencial"))


# ---------- Gemini (AI Studio y Vertex AI) ----------
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

    proveedor: ClassVar[str] = "gemini_api"

    def _disponibles(self) -> list[str]:
        """Modelos saturados recientemente van al final, para no esperar sus reintentos en
        cada consulta. Si todos lo están, se prueban igual."""
        ahora = time.monotonic()
        libres = [m for m in self.modelos if self._saturado_hasta.get(m, 0) <= ahora]
        return libres + [m for m in self.modelos if m not in libres]

    def _url(self, modelo: str) -> str:
        return f"{self.base_url}/models/{modelo}:generateContent"

    async def _cabeceras(self) -> dict:
        if not self.api_key:
            raise ErrorLLM("GEMINI_API_KEY no configurada")
        return {"x-goog-api-key": self.api_key}

    async def generar_json(self, sistema: str, prompt: str, esquema: dict) -> RespuestaLLM:
        cabeceras = await self._cabeceras()
        ultimo: ErrorLLM | None = None
        for modelo in self._disponibles():
            try:
                datos, uso = await self._generar(modelo, sistema, prompt, esquema, cabeceras)
                self._saturado_hasta.pop(modelo, None)
                return RespuestaLLM(datos, modelo, self.proveedor, uso)
            except ErrorLLM as exc:
                if not _es_saturacion(str(exc)):
                    raise
                self._saturado_hasta[modelo] = time.monotonic() + self.enfriamiento_s
                log.warning(
                    "LLM %s saturado; se usa respaldo por %.0fs", modelo, self.enfriamiento_s
                )
                ultimo = exc
        raise ultimo or ErrorLLM("Sin modelos configurados")

    async def _generar(
        self, modelo: str, sistema: str, prompt: str, esquema: dict, cabeceras: dict
    ) -> tuple[dict, Uso | None]:
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
                    cliente, self._url(modelo), cuerpo, cabeceras, self.reintentos
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
            return json.loads(texto), _uso_gemini(datos.get("usageMetadata"))
        except json.JSONDecodeError as exc:
            raise ErrorLLM(f"Respuesta no es JSON válido: {texto[:200]!r}") from exc


def _uso_gemini(meta: dict | None) -> Uso | None:
    if not meta:
        return None
    # El razonamiento («thoughts») se cobra como salida.
    salida = meta.get("candidatesTokenCount", 0) + meta.get("thoughtsTokenCount", 0)
    return Uso(meta.get("promptTokenCount", 0), salida)


@dataclass
class VertexLLM(GeminiLLM):
    """Gemini en Vertex AI: mismo formato de petición, otra URL y autenticación OAuth."""

    api_key: str = ""
    proyecto: str = ""
    region: str = "us-central1"
    credencial: CredencialGoogle | None = None

    proveedor: ClassVar[str] = "vertex"

    def _url(self, modelo: str) -> str:
        return vertex_url(self.proyecto, self.region, modelo, "generateContent")

    async def _cabeceras(self) -> dict:
        if not self.proyecto:
            raise ErrorLLM("VERTEX_PROYECTO no configurado")
        try:
            token = await (self.credencial or credencial_para("")).token()
        except ErrorCredencial as exc:
            raise ErrorLLM(f"Credencial de Google Cloud: {exc}") from exc
        return {"Authorization": f"Bearer {token}"}


# ---------- Claude (Anthropic) ----------
_CLAVES_ESQUEMA = ("type", "properties", "items", "required", "enum", "description")


def a_json_schema(esquema: dict) -> dict:
    """Esquema de Gemini (tipos en mayúsculas, OpenAPI) a JSON Schema para Claude: tipos en
    minúsculas y `additionalProperties: false` en cada objeto, como exigen las salidas
    estructuradas. Las restricciones que no admite se descartan."""
    if not esquema:
        return {"type": "object", "additionalProperties": False}
    salida: dict[str, Any] = {}
    for clave in _CLAVES_ESQUEMA:
        if clave not in esquema:
            continue
        valor = esquema[clave]
        if clave == "type":
            valor = str(valor).lower()
        elif clave == "properties":
            valor = {k: a_json_schema(v) for k, v in valor.items()}
        elif clave == "items":
            valor = a_json_schema(valor)
        salida[clave] = valor
    if esquema.get("nullable"):
        salida["type"] = [salida.get("type", "string"), "null"]
    if salida.get("type") == "object":
        salida["additionalProperties"] = False
    return salida


@dataclass
class ClaudeLLM:
    modelo: str
    api_key: str
    esfuerzo: str = "medium"
    timeout_s: float = 90.0
    reintentos: int = 1
    max_tokens: int = 16000
    cliente: Any = None  # inyectable en las pruebas

    proveedor: ClassVar[str] = "claude"

    def _cliente(self) -> Any:
        if self.cliente is None:
            if not self.api_key:
                raise ErrorLLM("ANTHROPIC_API_KEY no configurada")
            self.cliente = anthropic.AsyncAnthropic(
                api_key=self.api_key, timeout=self.timeout_s, max_retries=self.reintentos
            )
        return self.cliente

    async def generar_json(self, sistema: str, prompt: str, esquema: dict) -> RespuestaLLM:
        cliente = self._cliente()
        try:
            r = await cliente.beta.messages.create(
                model=self.modelo,
                max_tokens=self.max_tokens,
                system=sistema,
                messages=[{"role": "user", "content": prompt}],
                output_config={
                    "effort": self.esfuerzo,
                    "format": {"type": "json_schema", "schema": a_json_schema(esquema)},
                },
                # Si el modelo declina por una política de seguridad, la API reintenta en otro
                # modelo dentro de la misma llamada.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIStatusError as exc:
            raise ErrorLLM(f"HTTP {exc.status_code}: {str(exc.message)[:200]}") from exc
        except anthropic.APIConnectionError as exc:  # incluye APITimeoutError
            raise ErrorLLM(f"Proveedor inaccesible: {type(exc).__name__}") from exc

        if r.stop_reason == "refusal":
            categoria = getattr(r.stop_details, "category", None)
            raise ErrorLLM(f"El modelo no devolvió respuesta (rechazo: {categoria})")
        if r.stop_reason == "max_tokens":
            raise ErrorLLM("Respuesta incompleta: se alcanzó max_tokens")
        texto = "".join(b.text for b in r.content if b.type == "text")
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError as exc:
            raise ErrorLLM(f"Respuesta no es JSON válido: {texto[:200]!r}") from exc
        u = r.usage
        entrada = (
            u.input_tokens + (u.cache_creation_input_tokens or 0) + (u.cache_read_input_tokens or 0)
        )
        return RespuestaLLM(
            datos, r.model or self.modelo, self.proveedor, Uso(entrada, u.output_tokens)
        )


# ---------- Respaldo entre proveedores, cortacircuitos y costo ----------
@dataclass
class _Circuito:
    fallos: int = 0
    abierto_hasta: float = 0.0


@dataclass
class LLMConRespaldo:
    proveedores: list[tuple[str, ProveedorLLM]]
    costo: ControlDeCosto = field(default_factory=ControlDeCosto)
    fallos_para_abrir: int = 3
    abierto_s: float = 120.0
    _circuitos: dict[str, _Circuito] = field(default_factory=dict)

    def _circuito(self, nombre: str) -> _Circuito:
        return self._circuitos.setdefault(nombre, _Circuito())

    def _orden(self) -> list[tuple[str, ProveedorLLM]]:
        """Los de circuito abierto van al final: si todos están caídos se prueban igual."""
        ahora = time.monotonic()
        cerrados = [p for p in self.proveedores if self._circuito(p[0]).abierto_hasta <= ahora]
        return cerrados + [p for p in self.proveedores if p not in cerrados]

    def _fallo(self, nombre: str) -> None:
        c = self._circuito(nombre)
        c.fallos += 1
        if c.fallos >= self.fallos_para_abrir:
            c.abierto_hasta = time.monotonic() + self.abierto_s
            IA_CIRCUITO_ABIERTO.labels(nombre).set(1)
            log.error(
                "Proveedor de IA %s: %d fallos seguidos, se deja de usar por %.0fs",
                nombre,
                c.fallos,
                self.abierto_s,
            )

    def _exito(self, nombre: str) -> None:
        c = self._circuito(nombre)
        if c.fallos or c.abierto_hasta:
            IA_CIRCUITO_ABIERTO.labels(nombre).set(0)
        c.fallos, c.abierto_hasta = 0, 0.0

    async def generar_json(self, sistema: str, prompt: str, esquema: dict) -> RespuestaLLM:
        try:
            self.costo.verificar()
        except TopeDiarioAlcanzado as exc:
            log.error("%s", exc)
            raise ErrorTopeDiario(str(exc)) from exc
        ultimo: ErrorLLM | None = None
        anterior: str | None = None
        for nombre, proveedor in self._orden():
            try:
                r = await proveedor.generar_json(sistema, prompt, esquema)
            except ErrorLLM as exc:
                # Cualquier fallo pasa al siguiente proveedor (otro proveedor, otros modos de
                # fallar); solo los de disponibilidad cuentan para el cortacircuitos.
                if _no_disponible(str(exc)):
                    self._fallo(nombre)
                log.warning("Proveedor de IA %s falló: %s", nombre, str(exc)[:200])
                ultimo, anterior = exc, nombre
                continue
            self._exito(nombre)
            if anterior:
                IA_RESPALDOS.labels(anterior, nombre).inc()
            self.costo.registrar(r.proveedor or nombre, r.modelo, r.uso)
            return r
        raise ultimo or ErrorLLM("Sin proveedores de IA configurados")


def construir_llm(s) -> LLMConRespaldo:
    modelos = [s.llm_model, *[m for m in s.llm_modelos_respaldo if m != s.llm_model]]
    comun = dict(
        modelos=modelos,
        temperatura=s.llm_temperatura,
        timeout_s=s.llm_timeout_s,
        reintentos=s.llm_intentos_por_modelo,
    )
    principal: GeminiLLM
    if s.ia_proveedor == "vertex":
        principal = VertexLLM(
            **comun,
            proyecto=s.vertex_proyecto,
            region=s.vertex_region,
            credencial=credencial_para(s.vertex_credenciales),
        )
    else:
        principal = GeminiLLM(**comun, api_key=s.gemini_api_key, base_url=s.gemini_base_url)
    proveedores: list[tuple[str, ProveedorLLM]] = [(principal.proveedor, principal)]
    if s.llm_respaldo_proveedor == "claude":
        proveedores.append(
            ("claude", ClaudeLLM(s.claude_modelo, s.anthropic_api_key, esfuerzo=s.claude_esfuerzo))
        )
    IA_TOPE_DIARIO.set(s.ia_tope_diario_usd)
    return LLMConRespaldo(
        proveedores,
        ControlDeCosto(s.ia_tope_diario_usd, dict(s.ia_precios)),
        s.ia_cortacircuitos_fallos,
        s.ia_cortacircuitos_s,
    )


_llm: ProveedorLLM | None = None


def get_llm() -> ProveedorLLM:
    global _llm
    if _llm is None:
        _llm = construir_llm(get_settings())
    return _llm

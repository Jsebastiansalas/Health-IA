"""IA de producción (sprint 41): Vertex AI, Claude como respaldo, cortacircuitos y costo.

Todo sin red: Google y Anthropic se simulan (respx para HTTP, un cliente falso para el SDK).
"""

import json
import time
import uuid
from types import SimpleNamespace

import anthropic
import httpx
import httpx2
import jwt
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import Settings
from app.core.metricas import IA_COSTO, IA_RESPALDOS, IA_TOPE_RECHAZOS
from app.ia import costo as costo_mod
from app.ia import embeddings, google_auth
from app.ia.costo import ControlDeCosto, Uso
from app.ia.embeddings import VertexEmbeddings, construir_router
from app.ia.google_auth import CredencialGoogle, ErrorCredencial
from app.ia.llm import (
    ClaudeLLM,
    ErrorLLM,
    ErrorTopeDiario,
    GeminiLLM,
    LLMConRespaldo,
    RespuestaLLM,
    VertexLLM,
    a_json_schema,
    construir_llm,
)
from app.rag import explicar, generacion
from app.rag.busqueda import FragmentoRecuperado

TOKEN_URI = "https://oauth2.google.test/token"
VERTEX = "https://us-central1-aiplatform.googleapis.com/v1/projects/mi-proyecto/locations/us-central1/publishers/google/models"


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    async def _no_dormir(_):
        return None

    monkeypatch.setattr(embeddings.asyncio, "sleep", _no_dormir)


class TokenFijo:
    def __init__(self, token="tok-vertex"):
        self.valor = token
        self.pedidos = 0

    async def token(self):
        self.pedidos += 1
        return self.valor


# ---------- credencial de la cuenta de servicio ----------
@pytest.fixture
def cuenta(tmp_path):
    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = clave.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    ruta = tmp_path / "cuenta.json"
    ruta.write_text(
        json.dumps(
            {
                "type": "service_account",
                "client_email": "agente@mi-proyecto.iam.gserviceaccount.com",
                "private_key_id": "kid-1",
                "private_key": pem,
                "token_uri": TOKEN_URI,
            }
        ),
        encoding="utf-8",
    )
    return ruta, clave.public_key()


@respx.mock
async def test_la_cuenta_de_servicio_firma_un_jwt_y_el_token_se_guarda(cuenta):
    ruta, publica = cuenta
    ruta_token = respx.post(TOKEN_URI).mock(
        return_value=httpx.Response(200, json={"access_token": "ya29.x", "expires_in": 3600})
    )
    cred = CredencialGoogle(str(ruta))
    assert await cred.token() == "ya29.x"
    assert await cred.token() == "ya29.x"
    assert ruta_token.call_count == 1  # el segundo sale de la caché

    formulario = dict(httpx.QueryParams(ruta_token.calls.last.request.content.decode()))
    assert formulario["grant_type"] == "urn:ietf:params:oauth:grant-type:jwt-bearer"
    reclamos = jwt.decode(
        formulario["assertion"], publica, algorithms=["RS256"], audience=TOKEN_URI
    )
    assert reclamos["iss"] == "agente@mi-proyecto.iam.gserviceaccount.com"
    assert reclamos["scope"] == google_auth.ALCANCE
    # la clave privada nunca viaja: solo el JWT firmado
    assert "PRIVATE KEY" not in ruta_token.calls.last.request.content.decode()


@respx.mock
async def test_el_token_se_renueva_antes_de_vencer(cuenta):
    ruta, _ = cuenta
    ruta_token = respx.post(TOKEN_URI).mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 30})
    )
    cred = CredencialGoogle(str(ruta))
    await cred.token()
    await cred.token()  # dura menos que el margen: se pide otro
    assert ruta_token.call_count == 2


async def test_archivo_que_no_es_cuenta_de_servicio(tmp_path):
    ruta = tmp_path / "otra.json"
    ruta.write_text(json.dumps({"type": "authorized_user"}), encoding="utf-8")
    with pytest.raises(ErrorCredencial, match="cuenta de servicio"):
        await CredencialGoogle(str(ruta)).token()
    with pytest.raises(ErrorCredencial, match="No se pudo leer"):
        await CredencialGoogle(str(tmp_path / "no-existe.json")).token()


@respx.mock
async def test_sin_archivo_usa_el_servidor_de_metadatos():
    ruta = respx.get(url__regex=r"http://metadata\.google\.internal/.*").mock(
        return_value=httpx.Response(200, json={"access_token": "meta", "expires_in": 3599})
    )
    assert await CredencialGoogle("").token() == "meta"
    assert ruta.calls.last.request.headers["Metadata-Flavor"] == "Google"


@respx.mock
async def test_google_rechaza_la_credencial(cuenta):
    ruta, _ = cuenta
    respx.post(TOKEN_URI).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    with pytest.raises(ErrorCredencial, match="HTTP 400"):
        await CredencialGoogle(str(ruta)).token()


# ---------- Vertex: generación y embeddings ----------
def gemini_ok(datos: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"parts": [{"text": json.dumps(datos)}]}}],
            "usageMetadata": {
                "promptTokenCount": 1200,
                "candidatesTokenCount": 150,
                "thoughtsTokenCount": 50,
            },
        },
    )


@respx.mock
async def test_vertex_usa_la_url_del_proyecto_y_un_token_oauth():
    ruta = respx.post(f"{VERTEX}/gemini-2.5-flash:generateContent").mock(
        return_value=gemini_ok({"respuesta": "x"})
    )
    cred = TokenFijo()
    llm = VertexLLM(["gemini-2.5-flash"], proyecto="mi-proyecto", credencial=cred, reintentos=1)
    r = await llm.generar_json("sistema", "prompt", {"type": "OBJECT"})
    assert r.datos == {"respuesta": "x"} and r.proveedor == "vertex"
    assert r.uso == Uso(1200, 200)  # el razonamiento cuenta como salida
    peticion = ruta.calls.last.request
    assert peticion.headers["Authorization"] == "Bearer tok-vertex"
    assert "x-goog-api-key" not in peticion.headers
    assert json.loads(peticion.content)["generationConfig"]["responseSchema"] == {"type": "OBJECT"}


def test_vertex_global_no_lleva_la_region_en_el_host():
    llm = VertexLLM(["m"], proyecto="p", region="global")
    assert llm._url("m") == (
        "https://aiplatform.googleapis.com/v1/projects/p/locations/global"
        "/publishers/google/models/m:generateContent"
    )


async def test_vertex_sin_proyecto_o_sin_credencial():
    with pytest.raises(ErrorLLM, match="VERTEX_PROYECTO"):
        await VertexLLM(["m"]).generar_json("s", "p", {})

    class SinToken:
        async def token(self):
            raise ErrorCredencial("Google rechazó la credencial: HTTP 401")

    with pytest.raises(ErrorLLM, match="^Credencial"):
        await VertexLLM(["m"], proyecto="p", credencial=SinToken()).generar_json("s", "p", {})


@respx.mock
async def test_vertex_embeddings_un_texto_por_peticion_y_vectores_normalizados():
    def responder(request: httpx.Request) -> httpx.Response:
        cuerpo = json.loads(request.content)
        assert len(cuerpo["instances"]) == 1
        assert cuerpo["instances"][0]["task_type"] == "RETRIEVAL_DOCUMENT"
        assert cuerpo["parameters"] == {"outputDimensionality": 2}
        return httpx.Response(200, json={"predictions": [{"embeddings": {"values": [3.0, 4.0]}}]})

    ruta = respx.post(f"{VERTEX}/gemini-embedding-001:predict").mock(side_effect=responder)
    proveedor = VertexEmbeddings(
        "gemini-embedding-001", 2, proyecto="mi-proyecto", credencial=TokenFijo(), reintentos=1
    )
    vectores = await proveedor.embeber(["a", "b", "c"], "documento")
    assert vectores == [[0.6, 0.8]] * 3 and ruta.call_count == 3
    assert ruta.calls.last.request.headers["Authorization"] == "Bearer tok-vertex"


def test_con_vertex_el_modelo_de_embeddings_conserva_su_nombre():
    """Mismo modelo, otro proveedor: los expedientes ya indexados no se reindexan."""
    s = Settings(ia_proveedor="vertex", vertex_proyecto="p")
    router = construir_router(s)
    assert isinstance(router.proveedor("gemini-embedding-001"), VertexEmbeddings)
    assert router.modelos["gemini-embedding-001"] == 1536
    assert not isinstance(
        construir_router(Settings()).proveedor("gemini-embedding-001"), VertexEmbeddings
    )


# ---------- Claude como segundo proveedor ----------
def test_el_esquema_de_gemini_se_traduce_a_json_schema():
    convertido = a_json_schema(generacion.ESQUEMA)
    assert convertido["type"] == "object" and convertido["additionalProperties"] is False
    cita = convertido["properties"]["citas"]["items"]
    assert cita == {
        "type": "object",
        "properties": {"fragmento": {"type": "string"}, "extracto_literal": {"type": "string"}},
        "required": ["fragmento", "extracto_literal"],
        "additionalProperties": False,
    }
    assert a_json_schema({"type": "STRING", "nullable": True, "minLength": 3}) == {
        "type": ["string", "null"]
    }


class ClienteClaudeFalso:
    def __init__(self, respuesta=None, error=None):
        self.respuesta, self.error, self.pedidos = respuesta, error, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._crear))

    async def _crear(self, **kwargs):
        self.pedidos.append(kwargs)
        if self.error:
            raise self.error
        return self.respuesta


def mensaje_claude(texto="{}", stop_reason="end_turn", model="claude-opus-5-5", categoria=None):
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=texto),
        ],
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category=categoria) if categoria else None,
        model=model,
        usage=SimpleNamespace(
            input_tokens=900,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=100,
            output_tokens=300,
        ),
    )


async def test_claude_pide_json_estructurado_y_cuenta_los_tokens():
    cliente = ClienteClaudeFalso(mensaje_claude(json.dumps({"respuesta": "ok"})))
    r = await ClaudeLLM("claude-opus-5-5", "", cliente=cliente).generar_json(
        "sistema", "prompt", generacion.ESQUEMA
    )
    assert r == RespuestaLLM({"respuesta": "ok"}, "claude-opus-5-5", "claude", Uso(1000, 300))
    pedido = cliente.pedidos[0]
    assert pedido["model"] == "claude-opus-5-5" and pedido["system"] == "sistema"
    assert pedido["messages"] == [{"role": "user", "content": "prompt"}]
    assert pedido["output_config"]["format"]["schema"] == a_json_schema(generacion.ESQUEMA)
    assert pedido["output_config"]["effort"] == "medium"
    assert pedido["fallbacks"] == "default"


async def test_claude_rechazo_y_respuesta_cortada_son_errores():
    with pytest.raises(ErrorLLM, match="rechazo: bio"):
        await ClaudeLLM(
            "m",
            "",
            cliente=ClienteClaudeFalso(mensaje_claude(stop_reason="refusal", categoria="bio")),
        ).generar_json("s", "p", {})
    with pytest.raises(ErrorLLM, match="max_tokens"):
        await ClaudeLLM(
            "m", "", cliente=ClienteClaudeFalso(mensaje_claude(stop_reason="max_tokens"))
        ).generar_json("s", "p", {})


async def test_errores_del_sdk_se_traducen_como_los_de_gemini():
    peticion = httpx2.Request("POST", "https://api.anthropic.test/v1/messages")
    saturado = anthropic.InternalServerError(
        "Overloaded", response=httpx2.Response(529, request=peticion), body=None
    )
    with pytest.raises(ErrorLLM, match="^HTTP 529"):
        await ClaudeLLM("m", "", cliente=ClienteClaudeFalso(error=saturado)).generar_json(
            "s", "p", {}
        )
    caido = anthropic.APIConnectionError(request=peticion)
    with pytest.raises(ErrorLLM, match="^Proveedor inaccesible"):
        await ClaudeLLM("m", "", cliente=ClienteClaudeFalso(error=caido)).generar_json("s", "p", {})
    with pytest.raises(ErrorLLM, match="ANTHROPIC_API_KEY"):
        await ClaudeLLM("m", "").generar_json("s", "p", {})


# ---------- respaldo, cortacircuitos y costo ----------
class Proveedor:
    def __init__(self, nombre, *, error=None, datos=None, modelo="m", uso=Uso(1000, 100)):
        self.nombre, self.error, self.datos, self.modelo, self.uso = (
            nombre,
            error,
            datos,
            modelo,
            uso,
        )
        self.llamadas = 0

    async def generar_json(self, sistema, prompt, esquema):
        self.llamadas += 1
        if self.error:
            raise ErrorLLM(self.error)
        return RespuestaLLM(self.datos or {"de": self.nombre}, self.modelo, self.nombre, self.uso)


async def test_si_el_principal_falla_responde_el_respaldo():
    antes = IA_RESPALDOS.labels("vertex", "claude")._value.get()
    principal = Proveedor("vertex", error="HTTP 503: sobrecargado")
    llm = LLMConRespaldo([("vertex", principal), ("claude", Proveedor("claude"))])
    r = await llm.generar_json("s", "p", {})
    assert r.datos == {"de": "claude"}
    assert IA_RESPALDOS.labels("vertex", "claude")._value.get() == antes + 1


async def test_el_cortacircuitos_deja_de_insistir_y_vuelve_a_probar(monkeypatch):
    reloj = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: reloj[0])
    principal = Proveedor("vertex", error="Proveedor inaccesible: ConnectTimeout")
    llm = LLMConRespaldo(
        [("vertex", principal), ("claude", Proveedor("claude"))], fallos_para_abrir=2, abierto_s=60
    )
    for _ in range(4):
        await llm.generar_json("s", "p", {})
    assert principal.llamadas == 2  # tras dos fallos seguidos ya no se le envía nada

    reloj[0] += 61  # pasado el plazo se le da otra oportunidad
    principal.error = None
    r = await llm.generar_json("s", "p", {})
    assert r.datos == {"de": "vertex"} and principal.llamadas == 3


async def test_un_error_de_la_peticion_no_abre_el_circuito():
    principal = Proveedor("vertex", error="HTTP 400: esquema inválido")
    llm = LLMConRespaldo(
        [("vertex", principal), ("claude", Proveedor("claude"))], fallos_para_abrir=1
    )
    for _ in range(3):
        assert (await llm.generar_json("s", "p", {})).datos == {"de": "claude"}
    assert principal.llamadas == 3


async def test_si_todos_fallan_llega_el_ultimo_error():
    llm = LLMConRespaldo(
        [
            ("vertex", Proveedor("vertex", error="HTTP 503")),
            ("claude", Proveedor("claude", error="HTTP 529")),
        ]
    )
    with pytest.raises(ErrorLLM, match="HTTP 529"):
        await llm.generar_json("s", "p", {})


def test_costo_por_llamada_con_precios_de_referencia_y_propios():
    c = ControlDeCosto()
    # gemini-2.5-flash: 0,30 y 2,50 US$ por millón
    assert c.costo("gemini-2.5-flash", Uso(1_000_000, 100_000)) == pytest.approx(0.55)
    assert c.costo("claude-opus-5-5", Uso(1000, 300)) == pytest.approx(0.004 + 0.006)
    propio = ControlDeCosto(precios={"gemini-2.5-flash": (1.0, 1.0)})
    assert propio.costo("gemini-2.5-flash", Uso(500_000, 500_000)) == pytest.approx(1.0)
    # un modelo sin precio se cuenta caro, nunca gratis
    assert c.costo("modelo-nuevo", Uso(1_000_000, 0)) == pytest.approx(4.0)


async def test_el_tope_diario_corta_las_llamadas_hasta_el_otro_dia(monkeypatch):
    dia = ["2026-11-25"]
    monkeypatch.setattr(costo_mod, "_hoy", lambda: dia[0])
    gasto_antes = IA_COSTO.labels("vertex", "claude-opus-5-5")._value.get()
    rechazos_antes = IA_TOPE_RECHAZOS._value.get()
    proveedor = Proveedor("vertex", modelo="claude-opus-5-5", uso=Uso(100_000, 10_000))  # US$ 0,60
    llm = LLMConRespaldo([("vertex", proveedor)], ControlDeCosto(tope_diario_usd=1.0))

    await llm.generar_json("s", "p", {})
    await llm.generar_json("s", "p", {})  # llega a US$ 1,20: se pasa del tope con esta
    with pytest.raises(ErrorTopeDiario, match="Tope diario"):
        await llm.generar_json("s", "p", {})
    assert proveedor.llamadas == 2  # con el tope alcanzado no se llama al proveedor
    assert IA_TOPE_RECHAZOS._value.get() == rechazos_antes + 1
    assert IA_COSTO.labels("vertex", "claude-opus-5-5")._value.get() == pytest.approx(
        gasto_antes + 1.2
    )

    dia[0] = "2026-11-26"
    assert (await llm.generar_json("s", "p", {})).datos == {"de": "vertex"}


def _frag(texto):
    return FragmentoRecuperado(
        id=uuid.uuid4(),
        documento_id=uuid.uuid4(),
        orden=1,
        pagina_inicio=1,
        pagina_fin=1,
        seccion="",
        contenido_texto=texto,
        metadata={},
        nombre_archivo="d.pdf",
        tipo_documento="LABORATORIO",
        numero_adenda=0,
        sha256_original="0" * 64,
    )


async def test_las_garantias_valen_igual_si_responde_el_respaldo():
    """La salida del segundo proveedor pasa por las mismas comprobaciones deterministas."""
    inventada = {
        "hay_evidencia": True,
        "de_que_trata": "Un laboratorio.",
        "hallazgos": [
            {
                "texto": "La hemoglobina es 13,2 g/dL.",
                "fragmento": "F1",
                "extracto_literal": "Hemoglobina 13,2 g/dL",
            },
            {
                "texto": "La hemoglobina es 9,0 g/dL.",
                "fragmento": "F1",
                "extracto_literal": "Hemoglobina 13,2 g/dL",
            },
        ],
        "terminos": [{"termino": "Paracetamol", "explicacion": "Se toman 500 mg cada 8 horas."}],
        "senales_de_alarma": [],
        "preguntas_para_el_medico": [],
    }
    llm = LLMConRespaldo(
        [
            ("vertex", Proveedor("vertex", error="HTTP 503")),
            ("claude", Proveedor("claude", datos=inventada)),
        ]
    )
    salida = await llm.generar_json("s", "p", explicar.ESQUEMA_EXPLICAR)
    assert salida.proveedor == "claude"
    r = explicar.ensamblar_explicacion(
        salida.datos, [_frag("Hemoglobina 13,2 g/dL (ref 12,0 - 15,5).")], 0.85
    )
    assert [h["texto"] for h in r.hallazgos] == ["La hemoglobina es 13,2 g/dL."]
    assert "Paracetamol" not in [t["termino"] for t in r.terminos]


def test_construir_llm_segun_la_configuracion():
    desarrollo = construir_llm(Settings(gemini_api_key="k"))
    assert [n for n, _ in desarrollo.proveedores] == ["gemini_api"]
    assert type(desarrollo.proveedores[0][1]) is GeminiLLM

    produccion = construir_llm(
        Settings(
            ia_proveedor="vertex",
            vertex_proyecto="p",
            vertex_region="southamerica-east1",
            llm_respaldo_proveedor="claude",
            anthropic_api_key="sk-prueba",
            ia_tope_diario_usd=5,
        )
    )
    assert [n for n, _ in produccion.proveedores] == ["vertex", "claude"]
    vertex, claude = (p for _, p in produccion.proveedores)
    assert isinstance(vertex, VertexLLM) and vertex.region == "southamerica-east1"
    assert isinstance(claude, ClaudeLLM) and claude.modelo == "claude-opus-5-5"
    assert produccion.costo.tope_diario_usd == 5

"""Motor RAG: orquesta los Pasos 11 a 14 para una pregunta sobre un expediente."""

import logging
import time
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.ia.embeddings import EmbeddingRouter
from app.ia.llm import ProveedorLLM
from app.models import Expediente
from app.privacidad.anonimizar import Anonimizador, evidencias_para_la_nube
from app.rag import busqueda, generacion

log = logging.getLogger(__name__)


@dataclass
class RespuestaRag:
    resultado: generacion.ResultadoGeneracion
    modelo_embeddings: str
    modelo_llm: str | None
    fragmentos_recuperados: int
    latencia_ms: int


async def responder(
    session: AsyncSession,
    expediente: Expediente,
    pregunta: str,
    router: EmbeddingRouter,
    llm: ProveedorLLM,
    s: Settings,
) -> RespuestaRag:
    t0 = time.perf_counter()
    modelo = expediente.embedding_model_activo
    filtros = {
        "tenant_id": expediente.tenant_id,
        "expediente_id": expediente.id,
        "modelo": modelo,
    }

    # Paso 11: mismo modelo que el índice del expediente. La llamada a Gemini puede tardar
    # segundos: antes se devuelve la conexión a la base de datos (la autenticación y el permiso
    # ya abrieron una transacción). La sesión se reabre sola en la siguiente consulta.
    await session.close()
    # Privacidad: a la nube solo sale la pregunta enmascarada; la búsqueda léxica (en la base
    # propia) sigue usando la original. Lo mismo vale para las evidencias del prompt, más abajo.
    anon = Anonimizador() if s.anonimizar_antes_de_nube else None
    pregunta_nube = anon.enmascarar(pregunta) if anon else pregunta
    vector = await router.embeber_consulta(modelo, pregunta_nube)

    # Pasos 12-13: híbrida + RRF + reranking de dominio + vecinos.
    candidatos = await busqueda.busqueda_hibrida(
        session,
        **filtros,
        vector=vector,
        texto=pregunta,
        top_k=s.rag_top_k,
        rrf_k=s.rag_rrf_k,
        ef_search=s.rag_hnsw_ef_search,
        iterative=s.rag_hnsw_iterative,
    )
    evidencias = busqueda.reordenar(candidatos, s.rag_boost_adenda)[: s.rag_max_evidencias]
    await busqueda.expandir_vecinos(session, evidencias, **filtros)

    def _fin(resultado, modelo_llm) -> RespuestaRag:
        return RespuestaRag(
            resultado,
            modelo,
            modelo_llm,
            len(candidatos),
            int((time.perf_counter() - t0) * 1000),
        )

    if not evidencias:
        # Sin nada indexado o sin coincidencias: no se gasta una llamada al modelo.
        return _fin(generacion.ResultadoGeneracion(generacion.ABSTENCION, True), None)

    # Paso 14: generación fundamentada. Las evidencias son dataclasses (no ORM) y la generación
    # puede tardar hasta el timeout del modelo: no se retiene ninguna conexión mientras tanto.
    await session.close()
    evidencias_nube = evidencias_para_la_nube(evidencias, anon) if anon else evidencias
    salida = await llm.generar_json(
        generacion.SISTEMA,
        generacion.construir_prompt(pregunta_nube, evidencias_nube),
        generacion.ESQUEMA,
    )
    # Se restauran los datos en lo que devolvió el modelo y SOLO ENTONCES se verifican los extractos
    # contra los fragmentos originales: las citas siguen siendo literales.
    datos = anon.restaurar_json(salida.datos) if anon else salida.datos
    resultado = generacion.ensamblar(datos, evidencias, s.umbral_confianza_ocr)
    if resultado.citas_descartadas:
        log.warning(
            "Consulta expediente=%s: %d cita(s) con id inexistente descartadas",
            expediente.id,
            resultado.citas_descartadas,
        )
    return _fin(resultado, salida.modelo)


def a_json(r: RespuestaRag, consulta_id: uuid.UUID) -> dict:
    """Contrato de salida del documento de requerimientos (§5.E), en camelCase."""
    return {
        "consultaId": str(consulta_id),
        "respuestaAnalitica": r.resultado.respuesta,
        "sinEvidencia": r.resultado.sin_evidencia,
        "alertas": r.resultado.alertas,
        "citas": [
            {
                "documentoId": str(c.fragmento.documento_id),
                "nombreArchivo": c.fragmento.nombre_archivo,
                "tipoDocumento": c.fragmento.tipo_documento,
                "numeroAdenda": c.fragmento.numero_adenda,
                "sha256Original": c.fragmento.sha256_original,
                "paginaInicio": c.fragmento.pagina_inicio,
                "paginaFin": c.fragmento.pagina_fin,
                "seccion": c.fragmento.seccion,
                "orden": c.fragmento.orden,
                "extractoLiteral": c.extracto,
                "extractoAjustado": c.ajustado,
                "metodoExtraccion": c.fragmento.metadata.get("extraction_method", "NATIVE"),
                "confianzaOcr": c.fragmento.metadata.get("ocr_confidence"),
                "requiereVerificacionVisualOriginal": c.requiere_verificacion,
                "motivoVerificacionVisual": c.motivo_verificacion,
                "tiposEvidencia": c.tipos_evidencia,
            }
            for c in r.resultado.citas
        ],
        "modeloEmbeddings": r.modelo_embeddings,
        "modeloLlm": r.modelo_llm,
        "fragmentosRecuperados": r.fragmentos_recuperados,
        "latenciaMs": r.latencia_ms,
    }

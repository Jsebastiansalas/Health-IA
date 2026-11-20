package co.medtender.api;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** Consultas RAG y reindexacion: Java autoriza, limita y audita; el agente (simulado) responde. */
class ConsultasIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";
    private static final String RESPUESTA_RAG = """
            {"consultaId":"c-1","respuestaAnalitica":"La garantia es de doce meses.","sinEvidencia":false,
             "alertas":[],"citas":[{"documentoId":"d1","paginaInicio":4,"extractoLiteral":"garantia de doce meses"}],
             "modeloEmbeddings":"gemini-embedding-001","modeloLlm":"gemini-2.5-flash","fragmentosRecuperados":6,"latenciaMs":1234}
            """;

    private JsonNode admin;
    private String expediente;

    @BeforeEach
    void preparar() throws Exception {
        admin = registrarTenant("920001", "admin@q.co", PASS);
        expediente = crearExpediente(admin, "RAG-1");
        Infra.AGENTE.responder("POST /internal/v1/consultas", 200, RESPUESTA_RAG);
    }

    private org.springframework.test.web.servlet.ResultActions preguntar(JsonNode tokens, String exp, String pregunta) throws Exception {
        return mvc.perform(post("/api/v1/expedientes/" + exp + "/consultas").header("Authorization", bearer(tokens))
                .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("pregunta", pregunta))));
    }

    /** Un usuario del tenant con el permiso dado sobre el expediente; devuelve sus tokens. */
    private JsonNode usuarioConPermiso(String correo, String rol, String permiso) throws Exception {
        String id = crearUsuario(admin, correo, PASS, rol);
        mvc.perform(put("/api/v1/expedientes/" + expediente + "/permisos/" + id).header("Authorization", bearer(admin))
                .contentType(MediaType.APPLICATION_JSON).content("{\"permiso\":\"" + permiso + "\"}")).andExpect(status().isOk());
        return login(correo, PASS);
    }

    @Test
    void unLectorConsultaYLaRespuestaDelAgenteLlegaIntacta() throws Exception {
        JsonNode lector = usuarioConPermiso("lector@q.co", "LECTOR", "LECTOR");
        String idLector = cuerpo(mvc.perform(getAuth("/api/v1/auth/me", lector)).andReturn()).get("id").asText();

        preguntar(lector, expediente, "  ¿Cuál es la garantía?  ")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.respuestaAnalitica").value("La garantia es de doce meses."))
                .andExpect(jsonPath("$.citas[0].paginaInicio").value(4))
                .andExpect(jsonPath("$.latenciaMs").value(1234))
                .andExpect(header().string("Cache-Control", "no-store"));

        // El agente recibio la identidad ya autorizada y el token interno.
        var llamada = Infra.AGENTE.llamadas().stream().filter(l -> l.ruta().equals("/internal/v1/consultas")).findFirst().orElseThrow();
        assertThat(llamada.token()).isEqualTo(Infra.AGENTE_TOKEN);
        JsonNode enviado = json.readTree(llamada.cuerpo());
        assertThat(enviado.get("usuario_id").asText()).isEqualTo(idLector);
        assertThat(enviado.get("expediente_id").asText()).isEqualTo(expediente);
        assertThat(enviado.get("tenant_id").asText()).isEqualTo(cuerpo(mvc.perform(getAuth("/api/v1/auth/me", lector)).andReturn()).get("tenant_id").asText());
        assertThat(enviado.get("pregunta").asText()).contains("garantía");
    }

    @Test
    void laAuditoriaRegistraQuienConsultoPeroNuncaLaPregunta() throws Exception {
        preguntar(admin, expediente, "Pregunta secreta sobre el medicamento ZZZ").andExpect(status().isOk());
        var fila = jdbc.queryForMap("select detalle::text as detalle, resultado, recurso_tipo from auditoria where accion='CONSULTA_RAG'");
        String detalle = (String) fila.get("detalle");
        assertThat(detalle).contains("\"citas\": 1").contains("\"latencia_ms\": 1234").contains("c-1");
        assertThat(detalle).doesNotContain("secreta").doesNotContain("ZZZ");
        assertThat(fila.get("recurso_tipo")).isEqualTo("expediente");
    }

    @Test
    void sinPermisoOEnOtroTenantNoSeLlegaAlAgente() throws Exception {
        crearUsuario(admin, "sin@q.co", PASS, "AUDITOR_MEDICO");
        JsonNode sinPermiso = login("sin@q.co", PASS);
        JsonNode otro = registrarTenant("920002", "admin@r.co", PASS);

        preguntar(sinPermiso, expediente, "¿Garantías?").andExpect(status().isNotFound());
        preguntar(otro, expediente, "¿Garantías?").andExpect(status().isNotFound());
        mvc.perform(post("/api/v1/expedientes/" + expediente + "/consultas").contentType(MediaType.APPLICATION_JSON)
                .content("{\"pregunta\":\"hola\"}")).andExpect(status().isUnauthorized());
        assertThat(Infra.AGENTE.llamadas()).isEmpty();
    }

    @Test
    void preguntasInvalidasNoLlegan() throws Exception {
        preguntar(admin, expediente, "ab").andExpect(status().isUnprocessableEntity());
        preguntar(admin, expediente, "   ").andExpect(status().isUnprocessableEntity());
        preguntar(admin, expediente, "x".repeat(2001)).andExpect(status().isUnprocessableEntity());
        assertThat(Infra.AGENTE.llamadas()).isEmpty();
    }

    @Test
    void siElAgenteFallaElUsuarioVeUnMensajeGenericoSinDetallesInternos() throws Exception {
        for (int codigo : new int[] {500, 503, 401}) {
            Infra.AGENTE.responder("POST /internal/v1/consultas", codigo, "{\"detail\":\"HTTP 429 de Gemini, key AIza-secreta\"}");
            var r = preguntar(admin, expediente, "¿Garantías?").andExpect(status().isServiceUnavailable()).andReturn();
            assertThat(r.getResponse().getContentAsString()).contains("servicio de IA no está disponible")
                    .doesNotContain("Gemini").doesNotContain("AIza");
        }
    }

    @Test
    void erroresDeNegocioDelAgenteSeReenvian() throws Exception {
        Infra.AGENTE.responder("POST /internal/v1/consultas", 404, "{\"detail\":\"Expediente no encontrado\"}");
        preguntar(admin, expediente, "¿Garantías?").andExpect(status().isNotFound())
                .andExpect(jsonPath("$.detail").value("Expediente no encontrado"));
    }

    @Test
    void elLimitePorMinutoProtegeAlLlm() throws Exception {
        for (int i = 0; i < 20; i++) {
            preguntar(admin, expediente, "¿Garantías?").andExpect(status().isOk());
        }
        preguntar(admin, expediente, "¿Garantías?").andExpect(status().isTooManyRequests()).andExpect(header().exists("Retry-After"));
        // El rechazo no llego al agente.
        assertThat(Infra.AGENTE.llamadas()).hasSize(20);
    }

    @Test
    void historialSoloPideLasConsultasDelPropioUsuario() throws Exception {
        Infra.AGENTE.responder("GET /internal/v1/consultas", 200, "[{\"pregunta\":\"p\",\"consultaId\":\"c-1\"}]");
        String id = cuerpo(mvc.perform(getAuth("/api/v1/auth/me", admin)).andReturn()).get("id").asText();
        mvc.perform(getAuth("/api/v1/expedientes/" + expediente + "/consultas?limit=5", admin))
                .andExpect(status().isOk()).andExpect(jsonPath("$[0].consultaId").value("c-1"));
        var llamada = Infra.AGENTE.llamadas().get(0);
        assertThat(llamada.consulta()).contains("usuario_id=" + id).contains("expediente_id=" + expediente).contains("limit=5");
        mvc.perform(getAuth("/api/v1/expedientes/" + expediente + "/consultas?limit=1000", admin)).andExpect(status().isUnprocessableEntity());
    }

    // ---------- reindexacion ----------

    @Test
    void soloUnAdminDelExpedientePuedeReindexarYSeAudita() throws Exception {
        String cuerpoAgente = "{\"id\":\"r-1\",\"modelo_origen\":\"gemini-embedding-001\",\"modelo_destino\":\"bge-m3\",\"estado\":\"PENDIENTE\"}";
        Infra.AGENTE.responder("POST /internal/v1/reindexaciones", 202, cuerpoAgente);
        JsonNode editor = usuarioConPermiso("editor@q.co", "BIOMEDICO", "EDITOR");

        mvc.perform(post("/api/v1/expedientes/" + expediente + "/reindexaciones").header("Authorization", bearer(editor))
                .contentType(MediaType.APPLICATION_JSON).content("{\"embedding_model\":\"bge-m3\"}")).andExpect(status().isForbidden());
        assertThat(Infra.AGENTE.llamadas()).isEmpty();

        mvc.perform(post("/api/v1/expedientes/" + expediente + "/reindexaciones").header("Authorization", bearer(admin))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"embedding_model\":\"bge-m3\"}"))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.estado").value("PENDIENTE"))
                .andExpect(jsonPath("$.modelo_destino").value("bge-m3"));
        JsonNode enviado = json.readTree(Infra.AGENTE.llamadas().get(0).cuerpo());
        assertThat(enviado.get("embedding_model").asText()).isEqualTo("bge-m3");
        assertThat(jdbc.queryForObject("select count(*) from auditoria where accion='REINDEXACION_SOLICITADA'", Integer.class)).isEqualTo(1);
    }

    @Test
    void conflictosYModelosInvalidosDelAgenteSeReenvianConSuTexto() throws Exception {
        Infra.AGENTE.responder("POST /internal/v1/reindexaciones", 409, "{\"detail\":\"Ya hay una reindexación en curso\"}");
        mvc.perform(post("/api/v1/expedientes/" + expediente + "/reindexaciones").header("Authorization", bearer(admin))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"embedding_model\":\"bge-m3\"}"))
                .andExpect(status().isConflict()).andExpect(jsonPath("$.detail").value("Ya hay una reindexación en curso"));
        Infra.AGENTE.responder("POST /internal/v1/reindexaciones", 422, "{\"detail\":[{\"loc\":[\"body\"],\"msg\":\"x\"}]}");
        mvc.perform(post("/api/v1/expedientes/" + expediente + "/reindexaciones").header("Authorization", bearer(admin))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"embedding_model\":\"inventado\"}"))
                .andExpect(status().isUnprocessableEntity());
        mvc.perform(post("/api/v1/expedientes/" + expediente + "/reindexaciones").header("Authorization", bearer(admin))
                .contentType(MediaType.APPLICATION_JSON).content("{\"embedding_model\":\"\"}")).andExpect(status().isUnprocessableEntity());
    }

    @Test
    void listadoDeModelosYDeReindexaciones() throws Exception {
        Infra.AGENTE.responder("GET /internal/v1/embeddings/modelos", 200, "[{\"modelo\":\"bge-m3\",\"dimension\":1024}]");
        Infra.AGENTE.responder("GET /internal/v1/reindexaciones", 200, "[{\"id\":\"r-1\",\"estado\":\"COMPLETADA\"}]");
        mvc.perform(getAuth("/api/v1/embeddings/modelos", admin)).andExpect(status().isOk()).andExpect(jsonPath("$[0].dimension").value(1024));
        mvc.perform(get("/api/v1/embeddings/modelos")).andExpect(status().isUnauthorized());
        mvc.perform(getAuth("/api/v1/expedientes/" + expediente + "/reindexaciones", admin))
                .andExpect(status().isOk()).andExpect(jsonPath("$[0].estado").value("COMPLETADA"));
        JsonNode otro = registrarTenant("920003", "admin@s.co", PASS);
        mvc.perform(getAuth("/api/v1/expedientes/" + expediente + "/reindexaciones", otro)).andExpect(status().isNotFound());
    }
}

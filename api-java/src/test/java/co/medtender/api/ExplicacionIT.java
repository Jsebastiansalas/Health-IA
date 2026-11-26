package co.medtender.api;

import tools.jackson.databind.JsonNode;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** «Explícame este documento»: Java autoriza, exige consentimiento, limita y audita; el agente (simulado) explica. */
class ExplicacionIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";
    private static final String EXPLICACION = """
            {"consultaId":"c-9","modo":"explicar","documentoId":"d","deQueTrata":"Es un examen de sangre.",
             "hallazgos":[{"texto":"Hemoglobina 13,2","cita":1}],"terminos":[],"senalesDeAlarma":[],
             "preguntasParaElMedico":["¿Cada cuánto me controlo?"],"avisoGeneral":"Informativo.","sinEvidencia":false,
             "alertas":[],"citas":[{"documentoId":"d","extractoLiteral":"Hemoglobina 13,2 g/dL"}],"latenciaMs":900}
            """;

    private JsonNode admin;
    private String expediente;
    private String documento;

    @BeforeEach
    void preparar() throws Exception {
        admin = registrarTenant("930001", "admin@x.co", PASS);
        expediente = crearExpediente(admin, "EXP-1");
        documento = insertarDocumento(expediente, "Examen_Maria_Gomez.pdf");
        Infra.AGENTE.responder("POST /internal/v1/explicaciones", 200, EXPLICACION);
    }

    private String insertarDocumento(String exp, String nombre) {
        return jdbc.queryForObject("""
                insert into documentos (tenant_id, expediente_id, nombre_archivo_original, tipo_documento, sha256_original,
                                        tamano_bytes, estado_indexacion, embedding_model)
                select tenant_id, id, ?, 'HISTORIA_CLINICA', repeat('a', 64), 100, 'INDEXADO_Y_PURGADO', 'gemini-embedding-001'
                from expedientes where id = ?::uuid returning id::text
                """, String.class, nombre, exp);
    }

    private org.springframework.test.web.servlet.ResultActions explicar(JsonNode tokens, String exp, String doc) throws Exception {
        return mvc.perform(post("/api/v1/expedientes/" + exp + "/documentos/" + doc + "/explicacion")
                .header("Authorization", bearer(tokens)));
    }

    @Test
    void laExplicacionDelAgenteLlegaIntactaYElAgenteRecibeLaIdentidadAutorizada() throws Exception {
        explicar(admin, expediente, documento).andExpect(status().isOk())
                .andExpect(jsonPath("$.deQueTrata").value("Es un examen de sangre."))
                .andExpect(jsonPath("$.hallazgos[0].cita").value(1))
                .andExpect(header().string("Cache-Control", "no-store"));
        var llamada = Infra.AGENTE.llamadas().stream().filter(l -> l.ruta().equals("/internal/v1/explicaciones")).findFirst().orElseThrow();
        assertThat(llamada.token()).isEqualTo(Infra.AGENTE_TOKEN);
        JsonNode enviado = json.readTree(llamada.cuerpo());
        assertThat(enviado.get("documento_id").asString()).isEqualTo(documento);
        assertThat(enviado.get("expediente_id").asString()).isEqualTo(expediente);
    }

    @Test
    void laAuditoriaGuardaSoloIdsYConteos() throws Exception {
        explicar(admin, expediente, documento).andExpect(status().isOk());
        var fila = jdbc.queryForMap("select detalle::text as detalle, recurso_tipo from auditoria where accion='EXPLICACION_DOCUMENTO'");
        String detalle = (String) fila.get("detalle");
        assertThat(detalle).contains(documento).contains("\"citas\": 1");
        assertThat(detalle).doesNotContain("Hemoglobina").doesNotContain("Maria").doesNotContain("sangre");
        assertThat(fila.get("recurso_tipo")).isEqualTo("documento");
    }

    @Test
    void unDocumentoAjenoOInexistenteEsNoEncontradoYNoLlegaAlAgente() throws Exception {
        JsonNode otro = registrarTenant("930002", "admin@y.co", PASS);
        String expOtro = crearExpediente(otro, "EXP-2");
        String docOtro = insertarDocumento(expOtro, "otro.pdf");

        explicar(otro, expediente, documento).andExpect(status().isNotFound());       // expediente de otro tenant
        explicar(admin, expediente, docOtro).andExpect(status().isNotFound());        // documento de otro tenant
        explicar(admin, expediente, "00000000-0000-0000-0000-000000000000").andExpect(status().isNotFound());
        mvc.perform(post("/api/v1/expedientes/" + expediente + "/documentos/" + documento + "/explicacion"))
                .andExpect(status().isUnauthorized());
        assertThat(Infra.AGENTE.llamadas()).isEmpty();
    }

    @Test
    void laCuentaPersonalDebeAceptarElConsentimientoAntesDeExplicar() throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/auth/registro-personal").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("nombre", "Ana Pérez", "email", "ana@correo.co", "password", PASS)))).andReturn();
        JsonNode ana = cuerpo(r);
        String exp = crearExpediente(ana, "PERS-1");
        String doc = insertarDocumento(exp, "resultado.pdf");

        explicar(ana, exp, doc).andExpect(status().isForbidden()).andExpect(jsonPath("$.codigo").value("consentimiento_requerido"));
        assertThat(Infra.AGENTE.llamadas()).isEmpty();

        aceptarConsentimiento(ana).andExpect(status().isOk());
        explicar(ana, exp, doc).andExpect(status().isOk());
    }

    @Test
    void erroresDelAgenteSeTraducen() throws Exception {
        Infra.AGENTE.responder("POST /internal/v1/explicaciones", 409, "{\"detail\":\"El documento todavía se está procesando; intenta en un momento.\"}");
        explicar(admin, expediente, documento).andExpect(status().isConflict())
                .andExpect(jsonPath("$.detail").value("El documento todavía se está procesando; intenta en un momento."));
        Infra.AGENTE.responder("POST /internal/v1/explicaciones", 500, "{\"detail\":\"key AIza-secreta\"}");
        var r = explicar(admin, expediente, documento).andExpect(status().isServiceUnavailable()).andReturn();
        assertThat(r.getResponse().getContentAsString()).doesNotContain("AIza");
    }
}

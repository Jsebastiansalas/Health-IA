package co.medtender.api;

import com.fasterxml.jackson.databind.JsonNode;
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

/** «Preparar mi cita»: Java autoriza, exige consentimiento, limita y audita sin contenido; el agente (simulado) arma el resumen. */
class PreparacionCitaIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";
    private static final String RESUMEN = """
            {"consultaId":"c-11","modo":"preparacion","avisoGeneral":"No es un diagnóstico.",
             "eventos":[{"fecha":"2025-09-15","tipo":"EXAMEN","texto":"Resultados de laboratorio: Hb.","cita":1}],
             "cambios":[{"nombre":"Hemoglobina","mediciones":2,"desde":{"valorTexto":"13,2","cita":1},"hasta":{"valorTexto":"12,1","cita":2}}],
             "medicamentos":[{"nombre":"Atorvastatina","cita":3}],"diagnosticos":[],"alergias":[],
             "preguntas":["¿Cuándo debo repetir el perfil lipídico?"],"alertas":[],"citas":[{},{},{}],
             "sinEvidencia":false,"latenciaMs":1200}
            """;

    private JsonNode admin;
    private String expediente;

    @BeforeEach
    void preparar() throws Exception {
        admin = registrarTenant("960001", "admin@p.co", PASS);
        expediente = crearExpediente(admin, "EXP-P");
        Infra.AGENTE.responder("POST /internal/v1/preparaciones", 200, RESUMEN);
    }

    private org.springframework.test.web.servlet.ResultActions pedir(JsonNode tokens, String exp) throws Exception {
        return mvc.perform(post("/api/v1/expedientes/" + exp + "/preparacion").header("Authorization", bearer(tokens)));
    }

    @Test
    void elResumenLlegaIntactoYSeAuditaSinContenido() throws Exception {
        pedir(admin, expediente).andExpect(status().isOk())
                .andExpect(jsonPath("$.modo").value("preparacion"))
                .andExpect(jsonPath("$.preguntas[0]").value("¿Cuándo debo repetir el perfil lipídico?"))
                .andExpect(header().string("Cache-Control", "no-store"));
        var llamada = Infra.AGENTE.llamadas().stream().filter(l -> l.ruta().equals("/internal/v1/preparaciones")).findFirst().orElseThrow();
        assertThat(llamada.token()).isEqualTo(Infra.AGENTE_TOKEN);
        assertThat(json.readTree(llamada.cuerpo()).get("expediente_id").asText()).isEqualTo(expediente);
        String detalle = (String) jdbc.queryForMap("select detalle::text as detalle from auditoria where accion='PREPARACION_CITA'").get("detalle");
        assertThat(detalle).contains("\"preguntas\": 1").contains("\"medicamentos\": 1").contains("\"cambios\": 1");
        assertThat(detalle).doesNotContain("Atorvastatina").doesNotContain("lipídico").doesNotContain("13,2");
    }

    @Test
    void otroTenantOSinTokenNoLlegaAlAgente() throws Exception {
        JsonNode otro = registrarTenant("960002", "admin@p2.co", PASS);
        pedir(otro, expediente).andExpect(status().isNotFound());
        mvc.perform(post("/api/v1/expedientes/" + expediente + "/preparacion")).andExpect(status().isUnauthorized());
        assertThat(Infra.AGENTE.llamadas()).isEmpty();
    }

    @Test
    void laCuentaPersonalDebeAceptarElConsentimiento() throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/auth/registro-personal").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("nombre", "Ana Pérez", "email", "ana.p@correo.co", "password", PASS)))).andReturn();
        JsonNode ana = cuerpo(r);
        String exp = crearExpediente(ana, "PERS-P");
        pedir(ana, exp).andExpect(status().isForbidden()).andExpect(jsonPath("$.codigo").value("consentimiento_requerido"));
        assertThat(Infra.AGENTE.llamadas()).isEmpty();
        aceptarConsentimiento(ana).andExpect(status().isOk());
        pedir(ana, exp).andExpect(status().isOk());
    }

    @Test
    void erroresDelAgenteSeTraducen() throws Exception {
        Infra.AGENTE.responder("POST /internal/v1/preparaciones", 500, "{\"detail\":\"key AIza-secreta\"}");
        var r = pedir(admin, expediente).andExpect(status().isServiceUnavailable()).andReturn();
        assertThat(r.getResponse().getContentAsString()).doesNotContain("AIza");
    }
}

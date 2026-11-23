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

/** Cruce medicamentos de los documentos / fichas: Java autoriza, exige consentimiento, limita y audita; el agente (simulado) cruza. */
class CruceIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";
    private static final String CRUCE = """
            {"consultaId":"c-7","modo":"cruce","medicamentos":[{"nombre":"Ibuprofeno","cita":1}],"diagnosticos":[],"alergias":[],
             "advertencias":[{"texto":"La ficha advierte ulcera gastrica","medicamento":"Ibuprofeno","dato":"ulcera gastrica","citaMedicamento":1,"citaDato":2,"ficha":1}],
             "sinFicha":[],"avisoGeneral":"No indica dosis.","sinEvidencia":false,"alertas":[],"citas":[{},{}],"fichas":[{}],"latenciaMs":700}
            """;

    private JsonNode admin;
    private String expediente;

    @BeforeEach
    void preparar() throws Exception {
        admin = registrarTenant("940001", "admin@z.co", PASS);
        expediente = crearExpediente(admin, "EXP-C");
        Infra.AGENTE.responder("POST /internal/v1/cruces", 200, CRUCE);
    }

    private org.springframework.test.web.servlet.ResultActions cruzar(JsonNode tokens, String exp) throws Exception {
        return mvc.perform(post("/api/v1/expedientes/" + exp + "/medicamentos/cruce").header("Authorization", bearer(tokens)));
    }

    @Test
    void elCruceDelAgenteLlegaIntactoYSeAudita() throws Exception {
        cruzar(admin, expediente).andExpect(status().isOk())
                .andExpect(jsonPath("$.modo").value("cruce"))
                .andExpect(jsonPath("$.advertencias[0].ficha").value(1))
                .andExpect(header().string("Cache-Control", "no-store"));
        var llamada = Infra.AGENTE.llamadas().stream().filter(l -> l.ruta().equals("/internal/v1/cruces")).findFirst().orElseThrow();
        assertThat(llamada.token()).isEqualTo(Infra.AGENTE_TOKEN);
        assertThat(json.readTree(llamada.cuerpo()).get("expediente_id").asText()).isEqualTo(expediente);
        var fila = jdbc.queryForMap("select detalle::text as detalle, recurso_tipo from auditoria where accion='CRUCE_MEDICAMENTOS'");
        String detalle = (String) fila.get("detalle");
        assertThat(detalle).contains("\"medicamentos\": 1").contains("\"advertencias\": 1");
        assertThat(detalle).doesNotContain("Ibuprofeno").doesNotContain("ulcera");
        assertThat(fila.get("recurso_tipo")).isEqualTo("expediente");
    }

    @Test
    void otroTenantOSinTokenNoLlegaAlAgente() throws Exception {
        JsonNode otro = registrarTenant("940002", "admin@y2.co", PASS);
        cruzar(otro, expediente).andExpect(status().isNotFound());
        mvc.perform(post("/api/v1/expedientes/" + expediente + "/medicamentos/cruce")).andExpect(status().isUnauthorized());
        assertThat(Infra.AGENTE.llamadas()).isEmpty();
    }

    @Test
    void laCuentaPersonalDebeAceptarElConsentimientoAntesDelCruce() throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/auth/registro-personal").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("nombre", "Ana Pérez", "email", "ana@correo.co", "password", PASS)))).andReturn();
        JsonNode ana = cuerpo(r);
        String exp = crearExpediente(ana, "PERS-C");
        cruzar(ana, exp).andExpect(status().isForbidden()).andExpect(jsonPath("$.codigo").value("consentimiento_requerido"));
        assertThat(Infra.AGENTE.llamadas()).isEmpty();
        mvc.perform(post("/api/v1/consentimiento").header("Authorization", bearer(ana))).andExpect(status().isOk());
        cruzar(ana, exp).andExpect(status().isOk());
    }

    @Test
    void erroresDelAgenteSeTraducen() throws Exception {
        Infra.AGENTE.responder("POST /internal/v1/cruces", 500, "{\"detail\":\"key AIza-secreta\"}");
        var r = cruzar(admin, expediente).andExpect(status().isServiceUnavailable()).andReturn();
        assertThat(r.getResponse().getContentAsString()).doesNotContain("AIza");
    }
}

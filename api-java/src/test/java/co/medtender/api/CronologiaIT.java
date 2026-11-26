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

/** Línea de tiempo: Java autoriza, exige consentimiento, limita y audita sin contenido; el agente (simulado) la arma. */
class CronologiaIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";
    private static final String LINEA = """
            {"consultaId":"c-9","modo":"cronologia","guardada":false,
             "eventos":[{"fecha":"2025-09-15","fechaTexto":"15 de septiembre de 2025","tipo":"CONTROL","texto":"Control en 3 meses","cita":1}],
             "analitos":[{"clave":"hemoglobina","nombre":"Hemoglobina","unidades":["g/dL"],"comparable":true,
               "valores":[{"fecha":"2025-03-12","valor":13.2,"valorTexto":"13,2","cita":2}]}],
             "avisoGeneral":"No interpreta.","sinEvidencia":false,"alertas":[],"citas":[{},{}],"huella":"h","latenciaMs":900}
            """;

    private JsonNode admin;
    private String expediente;

    @BeforeEach
    void preparar() throws Exception {
        admin = registrarTenant("950001", "admin@t.co", PASS);
        expediente = crearExpediente(admin, "EXP-T");
        Infra.AGENTE.responder("POST /internal/v1/cronologias", 200, LINEA);
    }

    private org.springframework.test.web.servlet.ResultActions pedir(JsonNode tokens, String exp, String sufijo) throws Exception {
        return mvc.perform(post("/api/v1/expedientes/" + exp + "/cronologia" + sufijo).header("Authorization", bearer(tokens)));
    }

    @Test
    void laLineaDelAgenteLlegaIntactaYSeAuditaSinContenido() throws Exception {
        pedir(admin, expediente, "").andExpect(status().isOk())
                .andExpect(jsonPath("$.modo").value("cronologia"))
                .andExpect(jsonPath("$.analitos[0].valores[0].valor").value(13.2))
                .andExpect(header().string("Cache-Control", "no-store"));
        var llamada = Infra.AGENTE.llamadas().stream().filter(l -> l.ruta().equals("/internal/v1/cronologias")).findFirst().orElseThrow();
        assertThat(llamada.token()).isEqualTo(Infra.AGENTE_TOKEN);
        JsonNode enviado = json.readTree(llamada.cuerpo());
        assertThat(enviado.get("expediente_id").asString()).isEqualTo(expediente);
        assertThat(enviado.get("rehacer").asBoolean()).isFalse();
        var fila = jdbc.queryForMap("select detalle::text as detalle from auditoria where accion='LINEA_DE_TIEMPO'");
        String detalle = (String) fila.get("detalle");
        assertThat(detalle).contains("\"eventos\": 1").contains("\"examenes\": 1").contains("\"guardada\": false");
        assertThat(detalle).doesNotContain("Hemoglobina").doesNotContain("13,2").doesNotContain("septiembre");
    }

    @Test
    void rehacerViajaAlAgente() throws Exception {
        pedir(admin, expediente, "?rehacer=true").andExpect(status().isOk());
        var llamada = Infra.AGENTE.llamadas().stream().filter(l -> l.ruta().equals("/internal/v1/cronologias")).findFirst().orElseThrow();
        assertThat(json.readTree(llamada.cuerpo()).get("rehacer").asBoolean()).isTrue();
    }

    @Test
    void otroTenantOSinTokenNoLlegaAlAgente() throws Exception {
        JsonNode otro = registrarTenant("950002", "admin@t2.co", PASS);
        pedir(otro, expediente, "").andExpect(status().isNotFound());
        mvc.perform(post("/api/v1/expedientes/" + expediente + "/cronologia")).andExpect(status().isUnauthorized());
        assertThat(Infra.AGENTE.llamadas()).isEmpty();
    }

    @Test
    void laCuentaPersonalDebeAceptarElConsentimiento() throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/auth/registro-personal").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("nombre", "Ana Pérez", "email", "ana.t@correo.co", "password", PASS)))).andReturn();
        JsonNode ana = cuerpo(r);
        String exp = crearExpediente(ana, "PERS-T");
        pedir(ana, exp, "").andExpect(status().isForbidden()).andExpect(jsonPath("$.codigo").value("consentimiento_requerido"));
        assertThat(Infra.AGENTE.llamadas()).isEmpty();
        aceptarConsentimiento(ana).andExpect(status().isOk());
        pedir(ana, exp, "").andExpect(status().isOk());
    }

    @Test
    void erroresDelAgenteSeTraducen() throws Exception {
        Infra.AGENTE.responder("POST /internal/v1/cronologias", 500, "{\"detail\":\"key AIza-secreta\"}");
        var r = pedir(admin, expediente, "").andExpect(status().isServiceUnavailable()).andReturn();
        assertThat(r.getResponse().getContentAsString()).doesNotContain("AIza");
    }
}

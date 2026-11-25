package co.medtender.api;

import co.medtender.api.privacidad.CorreoEnvio;
import co.medtender.api.recordatorios.AvisosRecordatorios;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.ResultActions;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** Recordatorios: propuestas del agente (simulado) sin repetir, confirmación por la persona, .ics y aviso neutro. */
@Import(RecordatoriosIT.BuzonDePrueba.class)
class RecordatoriosIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";
    static final List<String[]> ENVIADOS = new CopyOnWriteArrayList<>();
    private static final String PROPUESTAS = """
            {"lineaGuardada":true,"propuestas":[
              {"texto":"Control en 3 meses con medicina interna","fechaTexto":"en 3 meses","fechaDocumento":"2025-09-15",
               "fechaPropuesta":"2025-12-15","cita":{"documentoId":"d1","nombreArchivo":"lab.pdf","paginaInicio":1,"extractoLiteral":"Control en 3 meses"}},
              {"texto":"Control con cardiología","fechaTexto":"","fechaDocumento":null,"fechaPropuesta":null,
               "cita":{"documentoId":"d2","nombreArchivo":"epicrisis.pdf","paginaInicio":2,"extractoLiteral":"Control con cardiología"}}
            ]}
            """;

    @TestConfiguration
    static class BuzonDePrueba {
        @Bean
        @Primary
        CorreoEnvio correoDePrueba() {
            return (para, asunto, cuerpo) -> ENVIADOS.add(new String[] {para, asunto, cuerpo});
        }
    }

    @Autowired
    AvisosRecordatorios avisos;

    private JsonNode admin;
    private String expediente;

    @BeforeEach
    void preparar() throws Exception {
        ENVIADOS.clear();
        admin = registrarTenant("970001", "admin@r.co", PASS);
        expediente = crearExpediente(admin, "EXP-R");
        Infra.AGENTE.responder("POST /internal/v1/recordatorios/propuestas", 200, PROPUESTAS);
    }

    private ResultActions proponer(JsonNode tokens, String exp) throws Exception {
        return mvc.perform(post("/api/v1/expedientes/" + exp + "/recordatorios/propuestas").header("Authorization", bearer(tokens)));
    }

    private ResultActions cambiar(JsonNode tokens, String id, Map<String, Object> cambio) throws Exception {
        return mvc.perform(patch("/api/v1/recordatorios/" + id).header("Authorization", bearer(tokens))
                .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(cambio)));
    }

    private JsonNode lista(JsonNode tokens) throws Exception {
        return cuerpo(mvc.perform(get("/api/v1/recordatorios").header("Authorization", bearer(tokens))).andReturn());
    }

    @Test
    void lasPropuestasSeGuardanSinRepetirseYSeAuditanSinContenido() throws Exception {
        proponer(admin, expediente).andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].estado").value("PROPUESTO"))
                .andExpect(jsonPath("$[0].fecha_propuesta").value("2025-12-15"))
                .andExpect(jsonPath("$[0].cita.nombreArchivo").value("lab.pdf"));
        proponer(admin, expediente).andExpect(jsonPath("$.length()").value(2)); // la segunda vez no duplica
        assertThat(jdbc.queryForObject("select count(*) from recordatorios", Integer.class)).isEqualTo(2);
        var detalles = jdbc.queryForList("select detalle::text from auditoria where accion='RECORDATORIOS_PROPUESTOS' order by created_at", String.class);
        assertThat(detalles.get(0)).contains("\"nuevas\": 2");
        assertThat(detalles.get(1)).contains("\"nuevas\": 0");
        assertThat(String.join(" ", detalles)).doesNotContain("medicina interna").doesNotContain("cardiología");
    }

    @Test
    void confirmarExigeFechaYDescartarLoQuitaDeLaLista() throws Exception {
        JsonNode props = cuerpo(proponer(admin, expediente).andReturn());
        String conFecha = props.get(0).get("id").asText();
        String sinFecha = props.get(1).get("id").asText();

        cambiar(admin, sinFecha, Map.of("estado", "CONFIRMADO")).andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.codigo").value("fecha_requerida"));
        cambiar(admin, sinFecha, Map.of("estado", "CONFIRMADO", "fecha", "2026-01-20")).andExpect(status().isOk())
                .andExpect(jsonPath("$.fecha").value("2026-01-20"));
        // sin fecha en la petición, confirma con la que propone el documento
        cambiar(admin, conFecha, Map.of("estado", "CONFIRMADO")).andExpect(status().isOk())
                .andExpect(jsonPath("$.fecha").value("2025-12-15"));
        cambiar(admin, conFecha, Map.of("estado", "DESCARTADO")).andExpect(status().isOk());
        JsonNode vigentes = lista(admin);
        assertThat(vigentes).hasSize(1);
        assertThat(vigentes.get(0).get("id").asText()).isEqualTo(sinFecha);
        assertThat(jdbc.queryForList("select detalle::text from auditoria where accion='RECORDATORIO_ACTUALIZADO'", String.class))
                .allSatisfy(d -> assertThat(d).doesNotContain("2026").doesNotContain("cardiología"));
    }

    @Test
    void otroTenantNoVeNiCambiaLosRecordatorios() throws Exception {
        String id = cuerpo(proponer(admin, expediente).andReturn()).get(0).get("id").asText();
        JsonNode otro = registrarTenant("970002", "admin@r2.co", PASS);
        cambiar(otro, id, Map.of("estado", "DESCARTADO")).andExpect(status().isNotFound());
        assertThat(lista(otro)).isEmpty();
        proponer(otro, expediente).andExpect(status().isNotFound());
        mvc.perform(get("/api/v1/recordatorios/" + id + "/calendario.ics").header("Authorization", bearer(otro)))
                .andExpect(status().isNotFound());
    }

    @Test
    void elCalendarioEsNeutroYSoloDeConfirmados() throws Exception {
        String id = cuerpo(proponer(admin, expediente).andReturn()).get(0).get("id").asText();
        mvc.perform(get("/api/v1/recordatorios/" + id + "/calendario.ics").header("Authorization", bearer(admin)))
                .andExpect(status().isConflict());
        cambiar(admin, id, Map.of("estado", "CONFIRMADO"));
        MvcResult r = mvc.perform(get("/api/v1/recordatorios/" + id + "/calendario.ics").header("Authorization", bearer(admin)))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith("text/calendar")).andReturn();
        String ics = r.getResponse().getContentAsString(java.nio.charset.StandardCharsets.UTF_8);
        assertThat(ics).contains("DTSTART;VALUE=DATE:20251215").contains("SUMMARY:Control médico");
        assertThat(ics).doesNotContain("medicina interna").doesNotContain("lab.pdf");
    }

    @Test
    void elAvisoLlegaUnaVezSinDatosDeSaludYVuelveSiCambiaLaFecha() throws Exception {
        JsonNode props = cuerpo(proponer(admin, expediente).andReturn());
        String cercano = props.get(1).get("id").asText();
        String lejano = props.get(0).get("id").asText();
        LocalDate hoy = LocalDate.of(2026, 1, 18);
        cambiar(admin, cercano, Map.of("estado", "CONFIRMADO", "fecha", "2026-01-20"));
        cambiar(admin, lejano, Map.of("estado", "CONFIRMADO", "fecha", "2026-03-01"));

        assertThat(avisos.enviarAvisos(hoy)).isEqualTo(1);
        assertThat(ENVIADOS).hasSize(1);
        String[] correo = ENVIADOS.get(0);
        assertThat(correo[0]).isEqualTo("admin@r.co");
        assertThat(correo[1]).isEqualTo("Tienes un recordatorio en MedTender");
        assertThat(correo[2]).contains("20 de enero de 2026").contains("/recordatorios")
                .doesNotContain("cardiología").doesNotContain("epicrisis");

        assertThat(avisos.enviarAvisos(hoy)).isZero(); // una sola vez
        cambiar(admin, cercano, Map.of("estado", "CONFIRMADO", "fecha", "2026-01-19"));
        assertThat(avisos.enviarAvisos(hoy)).isEqualTo(1); // cambió la fecha: se vuelve a avisar
        cambiar(admin, cercano, Map.of("estado", "HECHO"));
        assertThat(lista(admin).findValuesAsText("estado")).contains("HECHO");
    }

    @Test
    void laCuentaPersonalDebeAceptarElConsentimientoParaBuscarControles() throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/auth/registro-personal").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("nombre", "Ana Pérez", "email", "ana.r@correo.co", "password", PASS)))).andReturn();
        JsonNode ana = cuerpo(r);
        String exp = crearExpediente(ana, "PERS-R");
        proponer(ana, exp).andExpect(status().isForbidden()).andExpect(jsonPath("$.codigo").value("consentimiento_requerido"));
        mvc.perform(post("/api/v1/consentimiento").header("Authorization", bearer(ana))).andExpect(status().isOk());
        proponer(ana, exp).andExpect(status().isOk());
    }
}

package co.medtender.api;

import co.medtender.api.privacidad.RetencionService;
import tools.jackson.databind.JsonNode;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.ResultActions;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** La persona elige cuánto se conserva su historial; sin elegir, no se borra nada. */
class RetencionIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";

    @Autowired private RetencionService retencion;

    private JsonNode registrarPersonal(String email) throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/auth/registro-personal").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("nombre", "Ana Pérez", "email", email, "password", PASS)))).andReturn();
        assertThat(r.getResponse().getStatus()).isEqualTo(201);
        return cuerpo(r);
    }

    private ResultActions elegir(JsonNode tokens, String cuerpoJson) throws Exception {
        return mvc.perform(put("/api/v1/cuenta/retencion").header("Authorization", bearer(tokens))
                .contentType(MediaType.APPLICATION_JSON).content(cuerpoJson));
    }

    private void consultaDeHace(String expedienteId, String email, String intervalo, String pregunta) {
        var u = jdbc.queryForMap("select id, tenant_id from usuarios where email = ?", email);
        jdbc.update("""
                insert into consultas (tenant_id, expediente_id, usuario_id, pregunta, respuesta, sin_evidencia,
                    modelo_embeddings, latencia_ms, created_at)
                values (?, ?, ?, ?, '{}'::jsonb, false, 'gemini-embedding-001', 1, now() - ?::interval)""",
                u.get("tenant_id"), UUID.fromString(expedienteId), u.get("id"), pregunta, intervalo);
    }

    private java.util.List<String> preguntas() {
        return jdbc.queryForList("select pregunta from consultas order by pregunta", String.class);
    }

    @Test
    void sinElegirNadaNoSeBorraNada() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        String exp = crearExpediente(ana, "X-1");
        consultaDeHace(exp, "ana@correo.co", "30 months", "muy vieja");
        mvc.perform(getAuth("/api/v1/cuenta/retencion", ana)).andExpect(status().isOk())
                .andExpect(jsonPath("$.meses").isEmpty())
                .andExpect(jsonPath("$.se_borrarian['3']").value(1))
                .andExpect(jsonPath("$.se_borrarian['24']").value(1));
        assertThat(retencion.aplicar()).isZero();
        assertThat(preguntas()).containsExactly("muy vieja");
    }

    @Test
    void alElegirSeBorraLoMasAntiguoYSoloDeSuCuenta() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        String deAna = crearExpediente(ana, "X-1");
        consultaDeHace(deAna, "ana@correo.co", "7 months", "ana vieja");
        consultaDeHace(deAna, "ana@correo.co", "1 month", "ana reciente");
        JsonNode luis = registrarPersonal("luis@correo.co");
        consultaDeHace(crearExpediente(luis, "X-2"), "luis@correo.co", "7 months", "luis vieja");

        elegir(ana, "{\"meses\":6}").andExpect(status().isOk())
                .andExpect(jsonPath("$.meses").value(6)).andExpect(jsonPath("$.borradas").value(1));
        assertThat(preguntas()).containsExactly("ana reciente", "luis vieja");
        mvc.perform(getAuth("/api/v1/cuenta/retencion", ana)).andExpect(jsonPath("$.meses").value(6));
        assertThat(jdbc.queryForObject("select detalle::text from auditoria where accion='RETENCION_CAMBIADA'", String.class))
                .contains("\"meses\": 6", "\"borradas\": 1");
    }

    @Test
    void laTareaDiariaBorraLoQueVaVenciendo() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        String exp = crearExpediente(ana, "X-1");
        elegir(ana, "{\"meses\":3}").andExpect(status().isOk());
        consultaDeHace(exp, "ana@correo.co", "4 months", "ya venció");
        consultaDeHace(exp, "ana@correo.co", "2 months", "sigue");

        assertThat(retencion.aplicar()).isEqualTo(1);
        assertThat(preguntas()).containsExactly("sigue");
        assertThat(retencion.aplicar()).isZero();
    }

    @Test
    void sePuedeVolverAConservarTodo() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        String exp = crearExpediente(ana, "X-1");
        elegir(ana, "{\"meses\":3}").andExpect(status().isOk());
        elegir(ana, "{\"meses\":null}").andExpect(status().isOk()).andExpect(jsonPath("$.meses").isEmpty());
        consultaDeHace(exp, "ana@correo.co", "40 months", "se queda");
        assertThat(retencion.aplicar()).isZero();
    }

    @Test
    void soloValenLosPlazosOfrecidosYSoloEnCuentasPersonales() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        elegir(ana, "{\"meses\":1}").andExpect(status().isUnprocessableContent());
        elegir(ana, "{\"meses\":0}").andExpect(status().isUnprocessableContent());
        JsonNode admin = registrarTenant("930003", "admin@hospital.co", PASS);
        elegir(admin, "{\"meses\":6}").andExpect(status().isForbidden());
        mvc.perform(getAuth("/api/v1/cuenta/retencion", admin)).andExpect(status().isForbidden());
    }
}

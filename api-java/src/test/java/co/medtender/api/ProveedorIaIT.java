package co.medtender.api;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.ResultActions;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** El consentimiento nombra al proveedor de IA que el agente dice tener activo, no a uno supuesto. */
class ProveedorIaIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";

    private void agenteCon(String proveedor, String respaldo) {
        Infra.AGENTE.responder("GET /internal/v1/ia", 200,
                "{\"proveedor\":\"" + proveedor + "\",\"respaldo\":\"" + respaldo + "\"}");
    }

    private JsonNode registrarPersonal(String email) throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/auth/registro-personal").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("nombre", "Ana Pérez", "email", email, "password", PASS)))).andReturn();
        assertThat(r.getResponse().getStatus()).isEqualTo(201);
        return cuerpo(r);
    }

    private ResultActions aceptar(JsonNode tokens, String version) throws Exception {
        return mvc.perform(post("/api/v1/consentimiento").header("Authorization", bearer(tokens))
                .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("version", version))));
    }

    @Test
    void laVersionSigueAlProveedorActivoDelAgente() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        String[][] casos = {
                {"gemini_api", "", "2026-11-v3"},
                {"gemini_api", "claude", "2026-11-v3-claude"},
                {"vertex", "", "2026-11-v5"},
                {"vertex", "claude", "2026-11-v5-claude"},
        };
        for (String[] c : casos) {
            agenteCon(c[0], c[1]);
            mvc.perform(getAuth("/api/v1/consentimiento", ana)).andExpect(status().isOk())
                    .andExpect(jsonPath("$.version").value(c[2]))
                    .andExpect(jsonPath("$.proveedor_ia").value(c[0]))
                    .andExpect(jsonPath("$.respaldo_ia").value(c[1]));
        }
    }

    @Test
    void alCambiarDeProveedorHayQueAceptarDeNuevoAntesDeEnviarNada() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        String exp = crearExpediente(ana, "PERS-1");
        agenteCon("vertex", "");
        aceptar(ana, "2026-11-v5").andExpect(status().isOk()).andExpect(jsonPath("$.aceptado").value(true));

        agenteCon("gemini_api", "");
        mvc.perform(post("/api/v1/expedientes/" + exp + "/consultas").header("Authorization", bearer(ana))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of("pregunta", "¿Qué dice mi examen?"))))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.codigo").value("consentimiento_requerido"))
                .andExpect(jsonPath("$.version").value("2026-11-v3"));
        assertThat(Infra.AGENTE.llamadas()).isEmpty();
    }

    @Test
    void noSeRegistraLaAceptacionDeUnTextoQueYaCambio() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        // La persona tiene en pantalla el texto de la API gratuita, pero el agente ya cambió de proveedor.
        agenteCon("vertex", "claude");
        aceptar(ana, "2026-11-v3").andExpect(status().isConflict())
                .andExpect(jsonPath("$.codigo").value("consentimiento_cambio"))
                .andExpect(jsonPath("$.version").value("2026-11-v5-claude"));
        assertThat(jdbc.queryForObject("select count(*) from consentimientos", Integer.class)).isZero();
    }

    @Test
    void laPaginaPublicaDiceElProveedorSinSesion() throws Exception {
        agenteCon("vertex", "claude");
        mvc.perform(get("/api/v1/publico/ia")).andExpect(status().isOk())
                .andExpect(jsonPath("$.proveedor").value("vertex"))
                .andExpect(jsonPath("$.respaldo").value("claude"));
    }
}

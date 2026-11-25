package co.medtender.api;

import co.medtender.api.auth.Totp;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** Con la verificación en dos pasos obligatoria, un administrador de organización sin ella solo puede activarla. */
@TestPropertySource(properties = "medtender.seguridad.dos-pasos-admins=true")
class DosPasosObligatorioIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";

    @Test
    void elAdministradorDebeActivarlaAntesDeUsarLaApi() throws Exception {
        JsonNode admin = registrarTenant("990001", "admin@o.co", PASS);
        mvc.perform(get("/api/v1/expedientes").header("Authorization", bearer(admin)))
                .andExpect(status().isForbidden()).andExpect(jsonPath("$.codigo").value("dos_pasos_requerido"));
        mvc.perform(get("/api/v1/auth/me").header("Authorization", bearer(admin))).andExpect(status().isOk());

        JsonNode inicio = cuerpo(mvc.perform(post("/api/v1/auth/2fa/iniciar").header("Authorization", bearer(admin))).andReturn());
        mvc.perform(post("/api/v1/auth/2fa/activar").header("Authorization", bearer(admin)).contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of("codigo", Totp.codigoActual(inicio.get("secreto").asText(), Instant.now())))))
                .andExpect(status().isOk());
        mvc.perform(get("/api/v1/expedientes").header("Authorization", bearer(admin))).andExpect(status().isOk());
    }

    @Test
    void lasCuentasPersonalesYLosDemasRolesNoSeBloquean() throws Exception {
        JsonNode admin = registrarTenant("990002", "admin@o2.co", PASS);
        // Se activa para poder crear un usuario y luego se prueba ese usuario sin verificación en dos pasos.
        JsonNode inicio = cuerpo(mvc.perform(post("/api/v1/auth/2fa/iniciar").header("Authorization", bearer(admin))).andReturn());
        mvc.perform(post("/api/v1/auth/2fa/activar").header("Authorization", bearer(admin)).contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("codigo", Totp.codigoActual(inicio.get("secreto").asText(), Instant.now())))));
        crearUsuario(admin, "lector@o2.co", PASS, "LECTOR");
        JsonNode lector = login("lector@o2.co", PASS);
        mvc.perform(get("/api/v1/expedientes").header("Authorization", bearer(lector))).andExpect(status().isOk());

        JsonNode ana = cuerpo(mvc.perform(post("/api/v1/auth/registro-personal").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("nombre", "Ana Pérez", "email", "ana.o@correo.co", "password", PASS)))).andReturn());
        mvc.perform(get("/api/v1/expedientes").header("Authorization", bearer(ana))).andExpect(status().isOk());
    }
}

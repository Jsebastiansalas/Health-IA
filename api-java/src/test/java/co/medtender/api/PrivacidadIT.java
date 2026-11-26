package co.medtender.api;

import tools.jackson.databind.JsonNode;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** Cuentas personales, consentimiento informado y derecho de supresion. */
class PrivacidadIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";
    private static final String RESPUESTA_RAG = """
            {"consultaId":"c-1","respuestaAnalitica":"Resultado dentro de lo normal.","sinEvidencia":false,
             "alertas":[],"citas":[],"modeloEmbeddings":"gemini-embedding-001","modeloLlm":"gemini-2.5-flash",
             "fragmentosRecuperados":3,"latenciaMs":900}
            """;

    @BeforeEach
    void preparar() {
        Infra.AGENTE.responder("POST /internal/v1/consultas", 200, RESPUESTA_RAG);
    }

    private JsonNode registrarPersonal(String email) throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/auth/registro-personal").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("nombre", "Ana Pérez", "email", email, "password", PASS)))).andReturn();
        if (r.getResponse().getStatus() != 201) {
            throw new AssertionError("Registro personal fallido: " + r.getResponse().getStatus() + " " + r.getResponse().getContentAsString());
        }
        return cuerpo(r);
    }

    private org.springframework.test.web.servlet.ResultActions preguntar(JsonNode tokens, String exp) throws Exception {
        return mvc.perform(post("/api/v1/expedientes/" + exp + "/consultas").header("Authorization", bearer(tokens))
                .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("pregunta", "¿Qué dice mi examen?"))));
    }

    @Test
    void elRegistroPersonalCreaUnaCuentaPersonalConBorradoInmediato() throws Exception {
        registrarPersonal("ana@correo.co");
        var fila = jdbc.queryForMap("select tipo, politica_borrado, nit from tenants");
        assertThat(fila.get("tipo")).isEqualTo("PERSONAL");
        assertThat(fila.get("politica_borrado")).isEqualTo("INMEDIATO");
        assertThat(fila.get("nit").toString()).startsWith("P-");
        assertThat(jdbc.queryForObject("select count(*) from auditoria where accion='REGISTRO_PERSONAL'", Integer.class)).isEqualTo(1);
    }

    @Test
    void unCorreoRepetidoSeRechazaConConflicto() throws Exception {
        registrarPersonal("ana@correo.co");
        mvc.perform(post("/api/v1/auth/registro-personal").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("nombre", "Otra Ana", "email", "ana@correo.co", "password", PASS))))
                .andExpect(status().isConflict());
    }

    @Test
    void laCuentaPersonalDebeAceptarElConsentimientoAntesDeConsultar() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        String exp = crearExpediente(ana, "PERS-1");

        mvc.perform(getAuth("/api/v1/consentimiento", ana)).andExpect(status().isOk())
                .andExpect(jsonPath("$.requerido").value(true)).andExpect(jsonPath("$.aceptado").value(false));

        preguntar(ana, exp).andExpect(status().isForbidden())
                .andExpect(jsonPath("$.codigo").value("consentimiento_requerido"));
        assertThat(Infra.AGENTE.llamadas()).isEmpty(); // sin consentimiento no se llama al agente

        aceptarConsentimiento(ana).andExpect(status().isOk())
                .andExpect(jsonPath("$.aceptado").value(true));
        // Aceptar dos veces no duplica la constancia ni la auditoria.
        aceptarConsentimiento(ana).andExpect(status().isOk());
        assertThat(jdbc.queryForObject("select count(*) from consentimientos", Integer.class)).isEqualTo(1);
        assertThat(jdbc.queryForObject("select count(*) from auditoria where accion='CONSENTIMIENTO_ACEPTADO'", Integer.class)).isEqualTo(1);

        preguntar(ana, exp).andExpect(status().isOk());
    }

    @Test
    void unaOrganizacionNoNecesitaConsentimientoIndividual() throws Exception {
        JsonNode admin = registrarTenant("930001", "admin@hospital.co", PASS);
        String exp = crearExpediente(admin, "ORG-1");
        mvc.perform(getAuth("/api/v1/consentimiento", admin)).andExpect(jsonPath("$.requerido").value(false));
        preguntar(admin, exp).andExpect(status().isOk());
    }

    @Test
    void elConsentimientoDeUnaPersonaNoSeVeDesdeOtraCuenta() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        JsonNode luis = registrarPersonal("luis@correo.co");
        aceptarConsentimiento(ana).andExpect(status().isOk());
        mvc.perform(getAuth("/api/v1/consentimiento", luis)).andExpect(jsonPath("$.aceptado").value(false));
    }

    @Test
    void borrarElHistorialEliminaPreguntasYRespuestasGuardadas() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        String exp = crearExpediente(ana, "PERS-1");
        String tenant = jdbc.queryForObject("select id::text from tenants", String.class);
        String usuario = jdbc.queryForObject("select id::text from usuarios", String.class);
        jdbc.update("insert into consultas (tenant_id, expediente_id, usuario_id, pregunta, respuesta, sin_evidencia, modelo_embeddings, latencia_ms) "
                + "values (?::uuid, ?::uuid, ?::uuid, 'pregunta privada', '{}'::jsonb, false, 'gemini-embedding-001', 10)", tenant, exp, usuario);
        assertThat(jdbc.queryForObject("select count(*) from consultas", Integer.class)).isEqualTo(1);

        mvc.perform(delete("/api/v1/expedientes/" + exp + "/consultas").header("Authorization", bearer(ana)))
                .andExpect(status().isNoContent());
        assertThat(jdbc.queryForObject("select count(*) from consultas", Integer.class)).isZero();
        assertThat(jdbc.queryForObject("select count(*) from auditoria where accion='HISTORIAL_BORRADO'", Integer.class)).isEqualTo(1);
    }

    @Test
    void eliminarLaCuentaExigeLaContrasenaYBorraTodoMenosLaAuditoria() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        crearExpediente(ana, "PERS-1");
        aceptarConsentimiento(ana).andExpect(status().isOk());

        mvc.perform(post("/api/v1/cuenta/eliminar").header("Authorization", bearer(ana)).contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("password", "otra-clave-incorrecta")))).andExpect(status().isForbidden());
        assertThat(jdbc.queryForObject("select count(*) from tenants", Integer.class)).isEqualTo(1);

        mvc.perform(post("/api/v1/cuenta/eliminar").header("Authorization", bearer(ana)).contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("password", PASS)))).andExpect(status().isNoContent());

        for (String tabla : new String[] {"tenants", "usuarios", "expedientes", "consentimientos"}) {
            assertThat(jdbc.queryForObject("select count(*) from " + tabla, Integer.class)).as(tabla).isZero();
        }
        // La auditoria es de solo anexado y no guarda contenido: queda constancia de la eliminacion.
        assertThat(jdbc.queryForObject("select count(*) from auditoria where accion='CUENTA_ELIMINADA'", Integer.class)).isEqualTo(1);
        // Con la cuenta borrada ya no se puede entrar ni usar el token anterior.
        mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("email", "ana@correo.co", "password", PASS)))).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/auth/me").header("Authorization", bearer(ana))).andExpect(status().isUnauthorized());
    }

    @Test
    void unaOrganizacionNoPuedeEliminarseConEstaVia() throws Exception {
        JsonNode admin = registrarTenant("930002", "admin@clinica.co", PASS);
        mvc.perform(post("/api/v1/cuenta/eliminar").header("Authorization", bearer(admin)).contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("password", PASS)))).andExpect(status().isForbidden());
        assertThat(jdbc.queryForObject("select count(*) from tenants", Integer.class)).isEqualTo(1);
    }

    @Test
    void sinTokenNoSeAccedeAlConsentimiento() throws Exception {
        mvc.perform(get("/api/v1/consentimiento")).andExpect(status().isUnauthorized());
    }
}

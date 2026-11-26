package co.medtender.api;

import co.medtender.api.privacidad.CorreoEnvio;
import tools.jackson.databind.JsonNode;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MvcResult;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** Verificacion de correo de las cuentas personales (obligatoria en esta clase) con un buzon simulado. */
@TestPropertySource(properties = "medtender.correo.verificacion-obligatoria=true")
@Import(VerificacionCorreoIT.BuzonDePrueba.class)
class VerificacionCorreoIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";
    private static final Pattern ENLACE = Pattern.compile("verificar-correo\\?token=([0-9a-f]{64})");
    static final List<String[]> ENVIADOS = new CopyOnWriteArrayList<>();

    @TestConfiguration
    static class BuzonDePrueba {
        @Bean
        @Primary
        CorreoEnvio correoDePrueba() {
            return (para, asunto, cuerpo) -> ENVIADOS.add(new String[] {para, asunto, cuerpo});
        }
    }

    @BeforeEach
    void preparar() {
        ENVIADOS.clear();
        Infra.AGENTE.responder("POST /internal/v1/consultas", 200,
                "{\"consultaId\":\"c-1\",\"respuestaAnalitica\":\"ok\",\"sinEvidencia\":false,\"alertas\":[],\"citas\":[],\"latenciaMs\":1}");
    }

    private JsonNode registrarPersonal(String email) throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/auth/registro-personal").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("nombre", "Ana Pérez", "email", email, "password", PASS)))).andReturn();
        assertThat(r.getResponse().getStatus()).isEqualTo(201);
        return cuerpo(r);
    }

    private String tokenDelUltimoCorreo() {
        Matcher m = ENLACE.matcher(ENVIADOS.get(ENVIADOS.size() - 1)[2]);
        assertThat(m.find()).isTrue();
        return m.group(1);
    }

    private org.springframework.test.web.servlet.ResultActions verificar(String token) throws Exception {
        return mvc.perform(post("/api/v1/auth/verificar-correo").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("token", token))));
    }

    private org.springframework.test.web.servlet.ResultActions preguntar(JsonNode tokens, String exp) throws Exception {
        return mvc.perform(post("/api/v1/expedientes/" + exp + "/consultas").header("Authorization", bearer(tokens))
                .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("pregunta", "¿Qué dice mi examen?"))));
    }

    @Test
    void alRegistrarseSeEnviaUnEnlaceYHastaUsarloNoSePuedeConsultar() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        assertThat(ENVIADOS).hasSize(1);
        assertThat(ENVIADOS.get(0)[0]).isEqualTo("ana@correo.co");
        String exp = crearExpediente(ana, "PERS-1");

        mvc.perform(getAuth("/api/v1/consentimiento", ana)).andExpect(status().isOk())
                .andExpect(jsonPath("$.correo_requerido").value(true)).andExpect(jsonPath("$.correo_verificado").value(false));
        preguntar(ana, exp).andExpect(status().isForbidden()).andExpect(jsonPath("$.codigo").value("correo_no_verificado"));
        assertThat(Infra.AGENTE.llamadas()).isEmpty();

        verificar(tokenDelUltimoCorreo()).andExpect(status().isOk()).andExpect(jsonPath("$.verificado").value(true));
        mvc.perform(getAuth("/api/v1/consentimiento", ana)).andExpect(jsonPath("$.correo_verificado").value(true));
        // verificado el correo, sigue faltando el consentimiento (cada exigencia por separado)
        preguntar(ana, exp).andExpect(status().isForbidden()).andExpect(jsonPath("$.codigo").value("consentimiento_requerido"));
        aceptarConsentimiento(ana).andExpect(status().isOk());
        preguntar(ana, exp).andExpect(status().isOk());
    }

    @Test
    void elTokenNoSeGuardaEnClaroYElEnlaceEsIdempotente() throws Exception {
        registrarPersonal("ana@correo.co");
        String token = tokenDelUltimoCorreo();
        String guardado = jdbc.queryForObject("select token_hash from verificaciones_correo", String.class);
        assertThat(guardado).hasSize(64).isNotEqualTo(token);
        verificar(token).andExpect(status().isOk());
        verificar(token).andExpect(status().isOk()); // abrirlo dos veces no falla
    }

    @Test
    void unEnlaceInventadoOVencidoSeRechazaConUnMensajeClaro() throws Exception {
        registrarPersonal("ana@correo.co");
        verificar("0".repeat(64)).andExpect(status().isNotFound());
        String token = tokenDelUltimoCorreo();
        jdbc.update("update verificaciones_correo set expira_at = now() - interval '1 hour'");
        verificar(token).andExpect(status().isGone())
                .andExpect(jsonPath("$.detail").value("El enlace venció: pide uno nuevo desde la aplicación"));
        mvc.perform(post("/api/v1/auth/verificar-correo").contentType(MediaType.APPLICATION_JSON).content("{\"token\":\"\"}"))
                .andExpect(status().isUnprocessableContent());
    }

    @Test
    void sePuedeReenviarElEnlaceConLimiteYYaVerificadaNoSeEnviaNada() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        for (int i = 0; i < 3; i++) {
            mvc.perform(post("/api/v1/auth/reenviar-verificacion").header("Authorization", bearer(ana))).andExpect(status().isNoContent());
        }
        assertThat(ENVIADOS).hasSize(4);
        mvc.perform(post("/api/v1/auth/reenviar-verificacion").header("Authorization", bearer(ana))).andExpect(status().isTooManyRequests());
        verificar(tokenDelUltimoCorreo()).andExpect(status().isOk());
        int antes = ENVIADOS.size();
        mvc.perform(post("/api/v1/auth/reenviar-verificacion").header("Authorization", bearer(ana))).andExpect(status().isNoContent());
        assertThat(ENVIADOS).hasSize(antes);
        mvc.perform(post("/api/v1/auth/reenviar-verificacion")).andExpect(status().isUnauthorized());
    }

    @Test
    void lasOrganizacionesNoNecesitanVerificarCorreo() throws Exception {
        JsonNode admin = registrarTenant("950001", "admin@org.co", PASS);
        String exp = crearExpediente(admin, "ORG-1");
        mvc.perform(getAuth("/api/v1/consentimiento", admin)).andExpect(jsonPath("$.correo_requerido").value(false));
        preguntar(admin, exp).andExpect(status().isOk());
        assertThat(ENVIADOS).isEmpty();
    }
}

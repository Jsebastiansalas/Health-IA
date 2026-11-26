package co.medtender.api;

import co.medtender.api.auth.Totp;
import co.medtender.api.privacidad.CorreoEnvio;
import tools.jackson.databind.JsonNode;
import java.time.Instant;
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
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.ResultActions;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** Sprint 40: sesiones que rotan y se revocan, contraseña olvidada y cambiada, política y verificación en dos pasos. */
@Import(CuentasSegurasIT.BuzonDePrueba.class)
class CuentasSegurasIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";
    private static final String NUEVA = "Otra-Clave-Distinta-77";
    private static final Pattern ENLACE = Pattern.compile("restablecer\\?token=([0-9a-f]{64})");
    static final List<String[]> ENVIADOS = new CopyOnWriteArrayList<>();

    @TestConfiguration
    static class BuzonDePrueba {
        @Bean
        @Primary
        CorreoEnvio correoDePrueba() {
            return (para, asunto, cuerpo) -> ENVIADOS.add(new String[] {para, asunto, cuerpo});
        }
    }

    private JsonNode admin;

    @BeforeEach
    void preparar() throws Exception {
        ENVIADOS.clear();
        admin = registrarTenant("980001", "admin@c.co", PASS);
    }

    private ResultActions postJson(String url, Object cuerpo) throws Exception {
        return mvc.perform(post(url).contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(cuerpo)));
    }

    private ResultActions postAuth(String url, JsonNode tokens, Object cuerpo) throws Exception {
        return mvc.perform(post(url).header("Authorization", bearer(tokens)).contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(cuerpo)));
    }

    private ResultActions refresh(JsonNode tokens) throws Exception {
        return postJson("/api/v1/auth/refresh", Map.of("refresh_token", tokens.get("refresh_token").asString()));
    }

    private ResultActions me(JsonNode tokens) throws Exception {
        return mvc.perform(get("/api/v1/auth/me").header("Authorization", bearer(tokens)));
    }

    // ---------- Sesiones ----------

    @Test
    void renovarRotaElTokenYReutilizarUnoViejoCierraLaSesion() throws Exception {
        JsonNode nuevos = cuerpo(refresh(admin).andExpect(status().isOk()).andReturn());
        refresh(admin).andExpect(status().isUnauthorized()).andExpect(jsonPath("$.codigo").value("sesion_reutilizada"));
        // Toda la familia quedó revocada: tampoco sirve el token que se acababa de emitir.
        refresh(nuevos).andExpect(status().isUnauthorized());
        assertThat(jdbc.queryForObject("select count(*) from auditoria where accion='SESION_REUTILIZADA'", Integer.class)).isEqualTo(1);
    }

    @Test
    void cerrarSesionRevocaSuRenovacionYNoAfectaOtras() throws Exception {
        JsonNode otra = login("admin@c.co", PASS);
        postJson("/api/v1/auth/logout", Map.of("refresh_token", admin.get("refresh_token").asString())).andExpect(status().isNoContent());
        refresh(admin).andExpect(status().isUnauthorized());
        refresh(otra).andExpect(status().isOk());
        assertThat(jdbc.queryForObject("select count(*) from auditoria where accion = 'LOGOUT'", Integer.class)).isEqualTo(1);
        // Idempotente y sin revelar nada con un token inválido.
        postJson("/api/v1/auth/logout", Map.of("refresh_token", "basura")).andExpect(status().isNoContent());
    }

    @Test
    void cerrarTodasLasSesionesInvalidaYaLosTokensDeOtrosDispositivos() throws Exception {
        JsonNode otro = login("admin@c.co", PASS);
        JsonNode aqui = cuerpo(postAuth("/api/v1/auth/cerrar-sesiones", admin, Map.of()).andExpect(status().isOk()).andReturn());
        me(otro).andExpect(status().isUnauthorized());
        me(admin).andExpect(status().isUnauthorized());
        refresh(otro).andExpect(status().isUnauthorized());
        me(aqui).andExpect(status().isOk());
        refresh(aqui).andExpect(status().isOk());
    }

    // ---------- Contraseña ----------

    @Test
    void cambiarLaContrasenaExigeLaActualYUnaBuenaYCierraLasDemasSesiones() throws Exception {
        JsonNode otro = login("admin@c.co", PASS);
        postAuth("/api/v1/auth/cambiar-contrasena", admin, Map.of("actual", "no-es-esta-1", "nueva", NUEVA))
                .andExpect(status().isUnprocessableContent()).andExpect(jsonPath("$.codigo").value("contrasena_actual"));
        postAuth("/api/v1/auth/cambiar-contrasena", admin, Map.of("actual", PASS, "nueva", "contrasena123"))
                .andExpect(status().isUnprocessableContent()).andExpect(jsonPath("$.codigo").value("contrasena_comun"));
        JsonNode nuevos = cuerpo(postAuth("/api/v1/auth/cambiar-contrasena", admin, Map.of("actual", PASS, "nueva", NUEVA))
                .andExpect(status().isOk()).andReturn());
        me(otro).andExpect(status().isUnauthorized());
        me(nuevos).andExpect(status().isOk());
        login("admin@c.co", NUEVA);
        postJson("/api/v1/auth/login", Map.of("email", "admin@c.co", "password", PASS)).andExpect(status().isUnauthorized());
        assertThat(ENVIADOS).anySatisfy(c -> assertThat(c[1]).isEqualTo("Tu contraseña de MedTender cambió"));
    }

    @Test
    void olvideMiContrasenaNoRevelaCuentasYElEnlaceSirveUnaSolaVez() throws Exception {
        postJson("/api/v1/auth/olvide-contrasena", Map.of("email", "nadie@c.co")).andExpect(status().isAccepted());
        assertThat(ENVIADOS).isEmpty();
        String respuesta = postJson("/api/v1/auth/olvide-contrasena", Map.of("email", "ADMIN@c.co"))
                .andExpect(status().isAccepted()).andReturn().getResponse().getContentAsString();
        assertThat(respuesta).contains("Si hay una cuenta con ese correo");
        Matcher m = ENLACE.matcher(ENVIADOS.get(0)[2]);
        assertThat(m.find()).isTrue();
        String token = m.group(1);
        assertThat(jdbc.queryForObject("select count(*) from restablecimientos_clave where token_hash = ?", Integer.class, token)).isZero();

        postJson("/api/v1/auth/restablecer-contrasena", Map.of("token", token, "password", "1234567890"))
                .andExpect(status().isUnprocessableContent()).andExpect(jsonPath("$.codigo").value("contrasena_comun"));
        postJson("/api/v1/auth/restablecer-contrasena", Map.of("token", token, "password", NUEVA)).andExpect(status().isNoContent());
        postJson("/api/v1/auth/restablecer-contrasena", Map.of("token", token, "password", NUEVA))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.codigo").value("enlace_invalido"));
        me(admin).andExpect(status().isUnauthorized());
        login("admin@c.co", NUEVA);
    }

    @Test
    void unEnlaceVencidoNoSirve() throws Exception {
        postJson("/api/v1/auth/olvide-contrasena", Map.of("email", "admin@c.co"));
        Matcher m = ENLACE.matcher(ENVIADOS.get(0)[2]);
        assertThat(m.find()).isTrue();
        jdbc.update("update restablecimientos_clave set expira_at = now() - interval '1 minute'");
        postJson("/api/v1/auth/restablecer-contrasena", Map.of("token", m.group(1), "password", NUEVA))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.codigo").value("enlace_invalido"));
    }

    @Test
    void laPoliticaRechazaContrasenasComunesOConElCorreoAlRegistrarse() throws Exception {
        postJson("/api/v1/auth/registro-personal", Map.of("nombre", "Ana Pérez", "email", "ana.comun@correo.co", "password", "contrasena123"))
                .andExpect(status().isUnprocessableContent()).andExpect(jsonPath("$.codigo").value("contrasena_comun"));
        postJson("/api/v1/auth/registro-personal", Map.of("nombre", "Ana Pérez", "email", "anaperez@correo.co", "password", "anaperez-2026!"))
                .andExpect(status().isUnprocessableContent()).andExpect(jsonPath("$.codigo").value("contrasena_personal"));
    }

    // ---------- Verificación en dos pasos ----------

    private List<String> activarDosPasos(JsonNode tokens) throws Exception {
        JsonNode inicio = cuerpo(postAuth("/api/v1/auth/2fa/iniciar", tokens, Map.of()).andExpect(status().isOk()).andReturn());
        String secreto = inicio.get("secreto").asString();
        assertThat(inicio.get("uri").asString()).startsWith("otpauth://totp/MedTender").contains("secret=" + secreto);
        postAuth("/api/v1/auth/2fa/activar", tokens, Map.of("codigo", "000000"))
                .andExpect(status().isUnprocessableContent()).andExpect(jsonPath("$.codigo").value("codigo_invalido"));
        JsonNode r = cuerpo(postAuth("/api/v1/auth/2fa/activar", tokens, Map.of("codigo", Totp.codigoActual(secreto, Instant.now())))
                .andExpect(status().isOk()).andReturn());
        List<String> codigos = json.convertValue(r.get("codigos_respaldo"), json.getTypeFactory().constructCollectionType(List.class, String.class));
        codigos.add(0, secreto); // el primero es el secreto, para generar códigos en la prueba
        return codigos;
    }

    @Test
    void conDosPasosElIngresoPideUnCodigoDeLaAppODeRespaldo() throws Exception {
        List<String> datos = activarDosPasos(admin);
        String secreto = datos.get(0);
        String respaldo = datos.get(1);
        assertThat(datos).hasSize(11);
        assertThat(jdbc.queryForObject("select totp_secreto from usuarios where email='admin@c.co'", String.class))
                .startsWith("v1:").doesNotContain(secreto);
        me(admin).andExpect(jsonPath("$.dos_pasos").value(true));

        JsonNode paso1 = cuerpo(postJson("/api/v1/auth/login", Map.of("email", "admin@c.co", "password", PASS)).andExpect(status().isOk()).andReturn());
        assertThat(paso1.get("requiere2fa").asBoolean()).isTrue();
        assertThat(paso1.get("access_token").isNull()).isTrue();
        String desafio = paso1.get("desafio").asString();
        // El desafío no sirve como token de acceso.
        mvc.perform(get("/api/v1/auth/me").header("Authorization", "Bearer " + desafio)).andExpect(status().isUnauthorized());

        postJson("/api/v1/auth/2fa/verificar", Map.of("desafio", desafio, "codigo", "123456"))
                .andExpect(status().isUnauthorized()).andExpect(jsonPath("$.codigo").value("codigo_invalido"));
        JsonNode tokens = cuerpo(postJson("/api/v1/auth/2fa/verificar", Map.of("desafio", desafio, "codigo", Totp.codigoActual(secreto, Instant.now())))
                .andExpect(status().isOk()).andReturn());
        me(tokens).andExpect(status().isOk());

        // Un código de respaldo sirve una sola vez.
        postJson("/api/v1/auth/2fa/verificar", Map.of("desafio", desafio, "codigo", respaldo)).andExpect(status().isOk());
        postJson("/api/v1/auth/2fa/verificar", Map.of("desafio", desafio, "codigo", respaldo)).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/auth/2fa").header("Authorization", bearer(tokens)))
                .andExpect(jsonPath("$.activo").value(true)).andExpect(jsonPath("$.respaldos_disponibles").value(9));

        // Desactivar exige contraseña y código.
        postAuth("/api/v1/auth/2fa/desactivar", tokens, Map.of("password", "mala-clave-99", "codigo", Totp.codigoActual(secreto, Instant.now())))
                .andExpect(status().isUnprocessableContent());
        postAuth("/api/v1/auth/2fa/desactivar", tokens, Map.of("password", PASS, "codigo", Totp.codigoActual(secreto, Instant.now())))
                .andExpect(status().isNoContent());
        JsonNode sinDosPasos = login("admin@c.co", PASS);
        assertThat(sinDosPasos.get("access_token").asString()).isNotBlank();
        assertThat(ENVIADOS).extracting(c -> c[1]).contains(
                "Activaste la verificación en dos pasos en MedTender", "Desactivaste la verificación en dos pasos en MedTender");
    }

    @Test
    void elCodigoDeDosPasosTieneLimiteDeIntentos() throws Exception {
        activarDosPasos(admin);
        String desafio = cuerpo(postJson("/api/v1/auth/login", Map.of("email", "admin@c.co", "password", PASS)).andReturn()).get("desafio").asString();
        for (int i = 0; i < 5; i++) {
            postJson("/api/v1/auth/2fa/verificar", Map.of("desafio", desafio, "codigo", "000000")).andExpect(status().isUnauthorized());
        }
        postJson("/api/v1/auth/2fa/verificar", Map.of("desafio", desafio, "codigo", "000000")).andExpect(status().isTooManyRequests());
    }

    @Test
    void laAuditoriaDeCuentaNoGuardaSecretos() throws Exception {
        activarDosPasos(admin);
        postJson("/api/v1/auth/olvide-contrasena", Map.of("email", "admin@c.co"));
        MvcResult r = mvc.perform(get("/api/v1/auth/me").header("Authorization", bearer(admin))).andReturn();
        assertThat(r.getResponse().getStatus()).isEqualTo(200);
        assertThat(jdbc.queryForList("select detalle::text from auditoria", String.class))
                .allSatisfy(d -> assertThat(d).doesNotContain("otpauth").doesNotContain("token"));
    }
}

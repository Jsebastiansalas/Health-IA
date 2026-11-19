package co.medtender.api;

import com.fasterxml.jackson.databind.JsonNode;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.Map;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class IdentidadIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";

    // ---------- registro, login, me ----------

    @Test
    void registroLoginYMe() throws Exception {
        registrarTenant("900001", "admin@a.co", PASS);
        JsonNode t = login("ADMIN@a.co", PASS); // el correo no distingue mayusculas
        assertThat(t.get("token_type").asText()).isEqualTo("bearer");

        mvc.perform(getAuth("/api/v1/auth/me", t))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.email").value("admin@a.co"))
                .andExpect(jsonPath("$.rol_global").value("ADMIN_TENANT"))
                .andExpect(jsonPath("$.activo").value(true))
                .andExpect(jsonPath("$.tenant_id").exists())
                .andExpect(jsonPath("$.password_hash").doesNotExist());
    }

    @Test
    void registroDuplicadoDevuelve409() throws Exception {
        registrarTenant("900002", "admin@b.co", PASS);
        mvc.perform(post("/api/v1/auth/registro-tenant").contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of("tenant_nombre", "Otro", "nit", "900002",
                                "admin_email", "otro@b.co", "admin_password", PASS, "admin_nombre", "Otro"))))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.detail").value("El NIT o el email ya están registrados"));
    }

    @Test
    void contrasenaCortaDevuelve422() throws Exception {
        mvc.perform(post("/api/v1/auth/registro-tenant").contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of("tenant_nombre", "X Y", "nit", "900003",
                                "admin_email", "a@c.co", "admin_password", "corta", "admin_nombre", "Ana"))))
                .andExpect(status().isUnprocessableEntity());
    }

    @Test
    void contrasenaDeMasDe72BytesSeRechaza() throws Exception {
        mvc.perform(post("/api/v1/auth/registro-tenant").contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of("tenant_nombre", "X Y", "nit", "900004",
                                "admin_email", "a@d.co", "admin_password", "a".repeat(73), "admin_nombre", "Ana"))))
                .andExpect(status().isUnprocessableEntity());
    }

    // ---------- credenciales y bloqueo ----------

    @Test
    void credencialesInvalidasDan401SinRevelarSiElCorreoExiste() throws Exception {
        registrarTenant("900005", "admin@e.co", PASS);
        for (String email : new String[] {"admin@e.co", "noexiste@e.co"}) {
            mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                            .content(json.writeValueAsString(Map.of("email", email, "password", "incorrecta-123"))))
                    .andExpect(status().isUnauthorized())
                    .andExpect(jsonPath("$.detail").value("Credenciales inválidas"));
        }
    }

    @Test
    void tresFallosBloqueanElParIpCorreoYSeAudita() throws Exception {
        registrarTenant("900006", "admin@f.co", PASS);
        for (int i = 0; i < 3; i++) {
            mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                            .content(json.writeValueAsString(Map.of("email", "admin@f.co", "password", "mala-clave-1"))))
                    .andExpect(status().isUnauthorized());
        }
        // Cuarto intento, incluso con la clave correcta: bloqueado.
        mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of("email", "admin@f.co", "password", PASS))))
                .andExpect(status().isTooManyRequests())
                .andExpect(header().exists("Retry-After"));

        // Otro correo desde la misma IP no queda afectado.
        registrarTenant("900007", "otro@f.co", PASS);
        login("otro@f.co", PASS);

        Integer fallidos = jdbc.queryForObject("select count(*) from auditoria where accion='LOGIN_FALLIDO'", Integer.class);
        Integer bloqueados = jdbc.queryForObject("select count(*) from auditoria where accion='LOGIN_BLOQUEADO'", Integer.class);
        assertThat(fallidos).isEqualTo(3);
        assertThat(bloqueados).isEqualTo(1);
        // La auditoria nunca guarda la contrasena.
        Integer conClave = jdbc.queryForObject(
                "select count(*) from auditoria where detalle::text like '%mala-clave%' or detalle::text like '%Clave-Segura%'",
                Integer.class);
        assertThat(conClave).isZero();
    }

    // ---------- tokens ----------

    @Test
    void sinTokenOTokenInvalidoDan401() throws Exception {
        mvc.perform(get("/api/v1/auth/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.detail").value("No autenticado"));
        mvc.perform(get("/api/v1/auth/me").header("Authorization", "Bearer basura.basura.basura"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.detail").value("Token inválido o expirado"));
    }

    @Test
    void refreshNoSirveComoAccessYAccessNoSirveComoRefresh() throws Exception {
        JsonNode t = registrarTenant("900008", "admin@g.co", PASS);
        mvc.perform(get("/api/v1/auth/me").header("Authorization", "Bearer " + t.get("refresh_token").asText()))
                .andExpect(status().isUnauthorized());
        mvc.perform(post("/api/v1/auth/refresh").contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of("refresh_token", t.get("access_token").asText()))))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.detail").value("Refresh token inválido"));
    }

    @Test
    void refreshEmiteTokensNuevosConElRolActual() throws Exception {
        JsonNode t = registrarTenant("900009", "admin@h.co", PASS);
        mvc.perform(post("/api/v1/auth/refresh").contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of("refresh_token", t.get("refresh_token").asText()))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.access_token").exists());
    }

    @Test
    void usuarioDesactivadoPierdeAccesoDeInmediatoAunConTokenVigente() throws Exception {
        JsonNode admin = registrarTenant("900010", "admin@i.co", PASS);
        String id = crearUsuario(admin, "lector@i.co", PASS, "LECTOR");
        JsonNode lector = login("lector@i.co", PASS);
        mvc.perform(getAuth("/api/v1/auth/me", lector)).andExpect(status().isOk());

        mvc.perform(patch("/api/v1/usuarios/" + id).header("Authorization", bearer(admin))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"activo\":false}"))
                .andExpect(status().isOk());

        mvc.perform(getAuth("/api/v1/auth/me", lector))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.detail").value("Usuario inactivo o inexistente"));
        mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of("email", "lector@i.co", "password", PASS))))
                .andExpect(status().isUnauthorized());
    }

    // ---------- compatibilidad con el servicio Python anterior ----------

    @Test
    void hashBcryptGeneradoPorPythonSigueFuncionando() throws Exception {
        JsonNode admin = registrarTenant("900011", "admin@j.co", PASS);
        String tenantId = cuerpo(mvc.perform(getAuth("/api/v1/auth/me", admin)).andReturn()).get("tenant_id").asText();
        // Hash $2b$ producido por bcrypt de Python para "Contrasena-Python-1".
        jdbc.update("insert into usuarios (tenant_id, email, password_hash, nombre_completo, rol_global) "
                        + "values (?::uuid, 'python@j.co', ?, 'Usuario Python', 'LECTOR')", tenantId,
                "$2b$12$qe782edMEbUAwLMOUIzohezs/TsazTvJ4C4ZdJLgWdI84NHcUmHJ2");
        login("python@j.co", "Contrasena-Python-1");
    }

    @Test
    void tokenConElFormatoDePythonSeAcepta() throws Exception {
        JsonNode admin = registrarTenant("900012", "admin@k.co", PASS);
        JsonNode me = cuerpo(mvc.perform(getAuth("/api/v1/auth/me", admin)).andReturn());
        // Token armado a mano como lo hacia pyjwt: HS256, iat/exp numericos, claims sub/tenant_id/rol/type/jti.
        long ahora = Instant.now().getEpochSecond();
        String cabecera = b64("{\"alg\":\"HS256\",\"typ\":\"JWT\"}");
        String carga = b64("{\"sub\":\"" + me.get("id").asText() + "\",\"tenant_id\":\"" + me.get("tenant_id").asText()
                + "\",\"rol\":\"ADMIN_TENANT\",\"type\":\"access\",\"iat\":" + ahora + ",\"exp\":" + (ahora + 600)
                + ",\"jti\":\"abc123\"}");
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(JWT_SECRET.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        String firma = Base64.getUrlEncoder().withoutPadding()
                .encodeToString(mac.doFinal((cabecera + "." + carga).getBytes(StandardCharsets.UTF_8)));
        mvc.perform(get("/api/v1/auth/me").header("Authorization", "Bearer " + cabecera + "." + carga + "." + firma))
                .andExpect(status().isOk());
    }

    private static String b64(String s) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(s.getBytes(StandardCharsets.UTF_8));
    }

    // ---------- roles y aislamiento entre tenants ----------

    @Test
    void soloElAdminDelTenantAdministraUsuarios() throws Exception {
        JsonNode admin = registrarTenant("900013", "admin@l.co", PASS);
        crearUsuario(admin, "lector@l.co", PASS, "LECTOR");
        JsonNode lector = login("lector@l.co", PASS);

        mvc.perform(getAuth("/api/v1/usuarios", lector))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.detail").value("Rol sin autorización"));
        mvc.perform(post("/api/v1/usuarios").header("Authorization", bearer(lector))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of("email", "x@l.co", "password", PASS,
                                "nombre_completo", "Intruso", "rol_global", "ADMIN_TENANT"))))
                .andExpect(status().isForbidden());
        mvc.perform(getAuth("/api/v1/tenant", lector)).andExpect(status().isForbidden());
        mvc.perform(getAuth("/api/v1/auditoria", lector)).andExpect(status().isForbidden());
    }

    @Test
    void elAdminNoVeNiModificaUsuariosDeOtroTenant() throws Exception {
        JsonNode adminA = registrarTenant("900014", "admin@m.co", PASS);
        JsonNode adminB = registrarTenant("900015", "admin@n.co", PASS);
        String idB = crearUsuario(adminB, "lector@n.co", PASS, "LECTOR");

        mvc.perform(patch("/api/v1/usuarios/" + idB).header("Authorization", bearer(adminA))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"rol_global\":\"ADMIN_TENANT\"}"))
                .andExpect(status().isNotFound());

        MvcResult lista = mvc.perform(getAuth("/api/v1/usuarios", adminA)).andExpect(status().isOk()).andReturn();
        assertThat(cuerpo(lista)).hasSize(1);
        assertThat(cuerpo(lista).get(0).get("email").asText()).isEqualTo("admin@m.co");
    }

    @Test
    void emailDuplicadoEntreTenantsDa409() throws Exception {
        JsonNode adminA = registrarTenant("900016", "admin@o.co", PASS);
        JsonNode adminB = registrarTenant("900017", "admin@p.co", PASS);
        crearUsuario(adminA, "compartido@o.co", PASS, "LECTOR");
        mvc.perform(post("/api/v1/usuarios").header("Authorization", bearer(adminB))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of("email", "compartido@o.co", "password", PASS,
                                "nombre_completo", "Dup", "rol_global", "LECTOR"))))
                .andExpect(status().isConflict());
    }

    @Test
    void elAdminNoPuedeQuitarseSuPropioRol() throws Exception {
        JsonNode admin = registrarTenant("900018", "admin@q.co", PASS);
        String id = cuerpo(mvc.perform(getAuth("/api/v1/auth/me", admin)).andReturn()).get("id").asText();
        mvc.perform(patch("/api/v1/usuarios/" + id).header("Authorization", bearer(admin))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"rol_global\":\"LECTOR\"}"))
                .andExpect(status().isConflict());
        mvc.perform(patch("/api/v1/usuarios/" + id).header("Authorization", bearer(admin))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"activo\":false}"))
                .andExpect(status().isConflict());
    }

    @Test
    void tenantSeLeeYActualiza() throws Exception {
        JsonNode admin = registrarTenant("900019", "admin@r.co", PASS);
        mvc.perform(patch("/api/v1/tenant").header("Authorization", bearer(admin))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"nombre\":\"Nuevo Nombre\",\"politica_borrado\":\"DIFERIDO_1H\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.nombre").value("Nuevo Nombre"))
                .andExpect(jsonPath("$.politica_borrado").value("DIFERIDO_1H"));
        mvc.perform(getAuth("/api/v1/tenant", admin))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.nit").value("900019"));
    }

    // ---------- auditoria ----------

    @Test
    void auditoriaListaSoloEventosDelTenantYEsDeSoloAnexado() throws Exception {
        JsonNode adminA = registrarTenant("900020", "admin@s.co", PASS);
        JsonNode adminB = registrarTenant("900021", "admin@t.co", PASS);
        crearUsuario(adminA, "u@s.co", PASS, "LECTOR");
        crearUsuario(adminB, "u@t.co", PASS, "LECTOR");

        MvcResult r = mvc.perform(getAuth("/api/v1/auditoria?accion=USUARIO_CREADO", adminA))
                .andExpect(status().isOk()).andReturn();
        JsonNode eventos = cuerpo(r);
        assertThat(eventos).hasSize(1);
        assertThat(eventos.get(0).get("accion").asText()).isEqualTo("USUARIO_CREADO");
        assertThat(eventos.get(0).get("request_id").asText()).isNotBlank();

        // El trigger rechaza modificar o borrar la historia, incluso con acceso directo a la base.
        org.junit.jupiter.api.Assertions.assertThrows(org.springframework.dao.DataAccessException.class,
                () -> jdbc.update("update auditoria set resultado='ERROR'"));
        org.junit.jupiter.api.Assertions.assertThrows(org.springframework.dao.DataAccessException.class,
                () -> jdbc.update("delete from auditoria"));
    }

    @Test
    void filtrosInvalidosDeAuditoriaDan422() throws Exception {
        JsonNode admin = registrarTenant("900022", "admin@u.co", PASS);
        mvc.perform(getAuth("/api/v1/auditoria?resultado=XX", admin)).andExpect(status().isUnprocessableEntity());
        mvc.perform(getAuth("/api/v1/auditoria?limit=9999", admin)).andExpect(status().isUnprocessableEntity());
    }

    // ---------- operacion ----------

    @Test
    void cabecerasDeOperacion() throws Exception {
        mvc.perform(get("/api/v1/auth/me"))
                .andExpect(header().exists("X-Request-ID"))
                .andExpect(header().string("Cache-Control", "no-store"));
        mvc.perform(get("/api/v1/auth/me").header("X-Request-ID", "mi-id-123"))
                .andExpect(header().string("X-Request-ID", "mi-id-123"));
        // Un identificador con caracteres raros se reemplaza.
        MvcResult r = mvc.perform(get("/api/v1/auth/me").header("X-Request-ID", "mal id\twith\"bad")).andReturn();
        assertThat(r.getResponse().getHeader("X-Request-ID")).matches("[0-9a-f]{32}");
    }

    @Test
    void healthEsPublicoYMetricsExigeToken() throws Exception {
        mvc.perform(get("/health")).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("UP"));
        mvc.perform(get("/metrics")).andExpect(status().isUnauthorized());
        mvc.perform(get("/metrics").header("Authorization", "Bearer incorrecto")).andExpect(status().isUnauthorized());
        MvcResult ok = mvc.perform(get("/metrics").header("Authorization", "Bearer " + METRICS_TOKEN))
                .andExpect(status().isOk()).andReturn();
        assertThat(ok.getResponse().getContentAsString()).contains("jvm_memory_used_bytes");
    }
}

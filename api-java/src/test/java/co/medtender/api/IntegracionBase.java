package co.medtender.api;

import co.medtender.api.limites.AlmacenLimites;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.http.MediaType;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

/** Base de las pruebas de integracion: PostgreSQL+pgvector y Redis reales en contenedores. */
@SpringBootTest
@AutoConfigureMockMvc
@org.springframework.boot.test.autoconfigure.actuate.observability.AutoConfigureObservability
public abstract class IntegracionBase {

    public static final String JWT_SECRET = "secreto-de-pruebas-0123456789-abcdefghij-XYZ";
    public static final String METRICS_TOKEN = "token-metricas-de-prueba";

    static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer(
            DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"));
    static final GenericContainer<?> REDIS = new GenericContainer<>(DockerImageName.parse("redis:7-alpine"))
            .withExposedPorts(6379);

    static {
        POSTGRES.start();
        REDIS.start();
    }

    @DynamicPropertySource
    static void propiedades(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        r.add("spring.datasource.username", POSTGRES::getUsername);
        r.add("spring.datasource.password", POSTGRES::getPassword);
        r.add("spring.data.redis.url", () -> "redis://" + REDIS.getHost() + ":" + REDIS.getMappedPort(6379));
        r.add("medtender.jwt.secret", () -> JWT_SECRET);
        r.add("medtender.metrics-token", () -> METRICS_TOKEN);
        r.add("medtender.rate-limit.login-fallos-par", () -> "3");
        r.add("medtender.rate-limit.login-ip-min", () -> "1000");
        r.add("medtender.rate-limit.general-ip-min", () -> "100000");
    }

    @Autowired protected MockMvc mvc;
    @Autowired protected ObjectMapper json;
    @Autowired protected JdbcTemplate jdbc;
    @Autowired protected AlmacenLimites limites;

    @BeforeEach
    void limpiar() {
        jdbc.execute("TRUNCATE auditoria, usuarios, tenants CASCADE");
        limites.reiniciar();
    }

    protected JsonNode cuerpo(MvcResult r) throws Exception {
        return json.readTree(r.getResponse().getContentAsString());
    }

    /** Crea un tenant con su administrador y devuelve los tokens. */
    protected JsonNode registrarTenant(String nit, String email, String password) throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/auth/registro-tenant").contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of(
                                "tenant_nombre", "Hospital " + nit, "nit", nit, "admin_email", email,
                                "admin_password", password, "admin_nombre", "Admin " + nit))))
                .andReturn();
        if (r.getResponse().getStatus() != 201) {
            throw new AssertionError("Registro fallido: " + r.getResponse().getStatus() + " " + r.getResponse().getContentAsString());
        }
        return cuerpo(r);
    }

    protected JsonNode login(String email, String password) throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("email", email, "password", password)))).andReturn();
        if (r.getResponse().getStatus() != 200) {
            throw new AssertionError("Login fallido: " + r.getResponse().getStatus() + " " + r.getResponse().getContentAsString());
        }
        return cuerpo(r);
    }

    protected String bearer(JsonNode tokens) {
        return "Bearer " + tokens.get("access_token").asText();
    }

    /** Crea un usuario con el rol dado en el tenant del administrador y devuelve su id. */
    protected String crearUsuario(JsonNode tokensAdmin, String email, String password, String rol) throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/usuarios").header("Authorization", bearer(tokensAdmin))
                .contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("email", email, "password", password,
                        "nombre_completo", "Usuario " + rol, "rol_global", rol)))).andReturn();
        if (r.getResponse().getStatus() != 201) {
            throw new AssertionError("Alta fallida: " + r.getResponse().getStatus() + " " + r.getResponse().getContentAsString());
        }
        return cuerpo(r).get("id").asText();
    }

    protected org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder getAuth(String url, JsonNode tokens) {
        return get(url).header("Authorization", bearer(tokens));
    }
}

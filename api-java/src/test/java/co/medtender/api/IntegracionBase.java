package co.medtender.api;

import co.medtender.api.limites.AlmacenLimites;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.stream.Stream;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.actuate.observability.AutoConfigureObservability;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

/** Base de las pruebas con MockMvc: PostgreSQL+pgvector y Redis reales en contenedores. */
@SpringBootTest
@AutoConfigureMockMvc
@AutoConfigureObservability
public abstract class IntegracionBase {

    public static final String JWT_SECRET = Infra.JWT_SECRET;
    public static final String METRICS_TOKEN = Infra.METRICS_TOKEN;

    @DynamicPropertySource
    static void propiedades(DynamicPropertyRegistry r) {
        Infra.registrar(r);
    }

    @Autowired protected MockMvc mvc;
    @Autowired protected ObjectMapper json;
    /** Propietario de la base: ve todos los tenants. La aplicacion, en cambio, se conecta con `medtender_app`. */
    protected final JdbcTemplate jdbc = Infra.admin();
    @Autowired protected AlmacenLimites limites;

    @BeforeEach
    void limpiar() throws IOException {
        jdbc.execute("TRUNCATE auditoria, actas_purga, documentos, expedientes, usuarios, tenants CASCADE");
        limites.reiniciar();
        Infra.AGENTE.reiniciar();
        Infra.CLAMD.disponible(true);
        try (Stream<Path> archivos = Files.list(Infra.EFIMERO)) {
            archivos.forEach(p -> p.toFile().delete());
        }
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

    /** Acepta el consentimiento como lo hace la interfaz: con la versión que la API acaba de mostrar. */
    protected org.springframework.test.web.servlet.ResultActions aceptarConsentimiento(JsonNode tokens) throws Exception {
        String version = cuerpo(mvc.perform(getAuth("/api/v1/consentimiento", tokens)).andReturn()).get("version").asText();
        return mvc.perform(post("/api/v1/consentimiento").header("Authorization", bearer(tokens))
                .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("version", version))));
    }

    protected MockHttpServletRequestBuilder getAuth(String url, JsonNode tokens) {
        return get(url).header("Authorization", bearer(tokens));
    }

    /** Crea un expediente como el usuario dado y devuelve su id. */
    protected String crearExpediente(JsonNode tokens, String codigo) throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/expedientes").header("Authorization", bearer(tokens))
                .contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("codigo_expediente", codigo, "titulo", "Licitación " + codigo,
                        "entidad_contratante", "Hospital Central", "tipo_expediente", "LICITACION_MEDICAMENTOS"))))
                .andReturn();
        if (r.getResponse().getStatus() != 201) {
            throw new AssertionError("Expediente fallido: " + r.getResponse().getStatus() + " " + r.getResponse().getContentAsString());
        }
        return cuerpo(r).get("id").asText();
    }
}

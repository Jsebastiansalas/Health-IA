package co.medtender.api.config;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import org.springframework.boot.context.properties.ConfigurationProperties;

/** Configuracion propia de la aplicacion (prefijo {@code medtender}). */
@ConfigurationProperties(prefix = "medtender")
public record MedtenderProperties(
        String entorno,
        boolean confiarProxy,
        Jwt jwt,
        boolean allowTenantSignup,
        List<String> corsOrigins,
        String metricsToken,
        RateLimit rateLimit) {

    public record Jwt(String secret, int accessMinutes, int refreshDays) {}

    public record RateLimit(
            boolean habilitado,
            String backend,
            int generalIpMin,
            int loginIpMin,
            int loginFallosPar,
            int loginFallosVentanaS,
            int registroIpHora,
            int refreshIpMin,
            int consultaUsuarioMin,
            int consultaUsuarioDia,
            int subidaUsuarioHora,
            int reindexUsuarioHora) {}

    public boolean esProduccion() {
        return "produccion".equalsIgnoreCase(entorno);
    }

    /**
     * Revisa la configuracion de arranque. Devuelve {fatales, avisos}: los fatales impiden arrancar
     * en produccion (mismas reglas que el servicio Python original).
     */
    public List<List<String>> problemas() {
        List<String> fatales = new ArrayList<>();
        List<String> avisos = new ArrayList<>();
        String secreto = jwt.secret() == null ? "" : jwt.secret();
        if (secreto.length() < 32) {
            fatales.add("JWT_SECRET debe tener al menos 32 caracteres");
        } else if (secreto.contains("cambia-esto") || Set.copyOf(secreto.chars().boxed().toList()).size() < 10) {
            fatales.add("JWT_SECRET es el valor de ejemplo o demasiado simple");
        }
        if (rateLimit.habilitado() && "memoria".equals(rateLimit.backend())) {
            avisos.add("RATE_LIMIT_BACKEND=memoria no se comparte entre procesos");
        }
        if (!rateLimit.habilitado()) {
            avisos.add("RATE_LIMIT_HABILITADO=false: sin proteccion contra fuerza bruta");
        }
        if (allowTenantSignup) {
            avisos.add("ALLOW_TENANT_SIGNUP=true: cualquiera puede crear una organizacion");
        }
        if (corsOrigins.stream().anyMatch(o -> o.contains("localhost") || o.contains("127.0.0.1"))) {
            avisos.add("CORS_ORIGINS incluye localhost");
        }
        if (metricsToken == null || metricsToken.isBlank()) {
            avisos.add("METRICS_TOKEN vacio: /metrics queda deshabilitado");
        }
        if (!confiarProxy) {
            avisos.add("CONFIAR_PROXY=false: la IP del cliente sera la del proxy si hay uno delante");
        }
        return List.of(fatales, avisos);
    }
}

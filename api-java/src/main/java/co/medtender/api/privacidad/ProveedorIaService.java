package co.medtender.api.privacidad;

import co.medtender.api.ingesta.AgenteClient;
import tools.jackson.databind.JsonNode;
import java.time.Duration;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

/**
 * Que proveedor de IA recibe de verdad los datos. Se le pregunta al agente, que es quien los envia:
 * configurarlo tambien aqui permitiria que el consentimiento dijera una cosa y se hiciera otra.
 *
 * <p>La respuesta se guarda unos segundos. Si el agente no contesta se conserva la ultima (caido no envia
 * datos a nadie); si nunca contesto, o nombra un proveedor para el que no hay texto, no se supone ninguno.
 */
@Service
public class ProveedorIaService {

    private static final Logger log = LoggerFactory.getLogger(ProveedorIaService.class);
    private static final Set<String> PRINCIPALES = Set.of("gemini_api", "vertex");
    private static final Set<String> RESPALDOS = Set.of("", "claude");

    public record Proveedor(String principal, String respaldo) {}

    private record Guardado(Proveedor proveedor, long hasta) {}

    private final AgenteClient agente;
    private final long plazoNanos;
    private volatile Guardado guardado;

    public ProveedorIaService(AgenteClient agente, @Value("${medtender.ia.proveedor-ttl-s:15}") long plazoSegundos) {
        this.agente = agente;
        this.plazoNanos = Duration.ofSeconds(plazoSegundos).toNanos();
    }

    public Optional<Proveedor> actual() {
        Guardado g = guardado;
        if (g != null && System.nanoTime() - g.hasta() < 0) {
            return Optional.of(g.proveedor());
        }
        JsonNode r;
        try {
            r = agente.get("/internal/v1/ia", Map.of());
        } catch (RuntimeException e) {
            log.warn("No se pudo preguntar al agente por el proveedor de IA: {}", e.getMessage());
            return Optional.ofNullable(g).map(Guardado::proveedor);
        }
        String principal = r == null ? "" : r.path("proveedor").asString("");
        String respaldo = r == null ? "" : r.path("respaldo").asString("");
        if (!PRINCIPALES.contains(principal) || !RESPALDOS.contains(respaldo)) {
            log.error("El agente informa un proveedor de IA sin texto de consentimiento: '{}' / '{}'", principal, respaldo);
            guardado = null;
            return Optional.empty();
        }
        var proveedor = new Proveedor(principal, respaldo);
        guardado = new Guardado(proveedor, System.nanoTime() + plazoNanos);
        return Optional.of(proveedor);
    }
}

package co.medtender.api.ia;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.config.MedtenderProperties;
import co.medtender.api.domain.Permiso;
import co.medtender.api.expediente.AutorizacionExpediente;
import co.medtender.api.ingesta.AgenteClient;
import co.medtender.api.limites.Limitador;
import co.medtender.api.security.UsuarioActual;
import tools.jackson.databind.JsonNode;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Consola RAG. Java autoriza (permiso LECTOR sobre el expediente), limita y audita; el agente de
 * IA (Python) busca, genera la respuesta y arma las citas verificables.
 */
@RestController
@RequestMapping("/api/v1/expedientes/{expedienteId}/consultas")
public class ConsultaController {

    public record PreguntaIn(@NotBlank @Size(min = 3, max = 2000) String pregunta) {}

    private final AutorizacionExpediente autorizacion;
    private final AgenteClient agente;
    private final Limitador limitador;
    private final AuditoriaService auditoria;
    private final MedtenderProperties props;

    public ConsultaController(AutorizacionExpediente autorizacion, AgenteClient agente, Limitador limitador,
                              AuditoriaService auditoria, MedtenderProperties props) {
        this.autorizacion = autorizacion;
        this.agente = agente;
        this.limitador = limitador;
        this.auditoria = auditoria;
        this.props = props;
    }

    /**
     * Respuesta con respuestaAnalitica, citas (documento, pagina, SHA-256, extracto literal,
     * alertas probatorias) y alertas. Requiere permiso LECTOR sobre el expediente.
     */
    @org.springframework.beans.factory.annotation.Autowired
    private co.medtender.api.privacidad.ConsentimientoService consentimiento;

    @PostMapping
    public JsonNode consultar(@PathVariable UUID expedienteId, @Valid @RequestBody PreguntaIn in,
                              @AuthenticationPrincipal UsuarioActual user) {
        UUID tenant = autorizacion.obtenerCompartible(user, expedienteId, Permiso.LECTOR).expediente().getTenantId();
        consentimiento.exigir(user);
        // Cada pregunta cuesta una llamada de embeddings y otra al modelo generativo.
        var rl = props.rateLimit();
        limitador.exigir("consulta_min", user.id().toString(), rl.consultaUsuarioMin(), 60);
        limitador.exigir("consulta_dia", user.id().toString(), rl.consultaUsuarioDia(), 86400);

        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("tenant_id", tenant);
        cuerpo.put("expediente_id", expedienteId);
        cuerpo.put("usuario_id", user.id());
        cuerpo.put("pregunta", in.pregunta());
        JsonNode respuesta = agente.post("/internal/v1/consultas", cuerpo, true);

        // Se audita quien consulto que expediente y con que resultado; nunca el texto de la pregunta.
        Map<String, Object> detalle = new LinkedHashMap<>();
        detalle.put("consulta", respuesta.path("consultaId").asString(null));
        detalle.put("sin_evidencia", respuesta.path("sinEvidencia").asBoolean(false));
        detalle.put("citas", respuesta.path("citas").size());
        detalle.put("latencia_ms", respuesta.path("latenciaMs").asLong(0));
        auditoria.auditar(Accion.CONSULTA_RAG, user, "expediente", expedienteId, detalle);
        return respuesta;
    }

    /** Consultas propias del usuario en el expediente, la mas reciente primero. */
    @GetMapping
    public JsonNode historial(@PathVariable UUID expedienteId, @AuthenticationPrincipal UsuarioActual user,
                              @RequestParam(defaultValue = "20") @Min(1) @Max(100) int limit) {
        UUID tenant = autorizacion.obtenerCompartible(user, expedienteId, Permiso.LECTOR).expediente().getTenantId();
        return agente.get("/internal/v1/consultas", Map.of("tenant_id", tenant,
                "expediente_id", expedienteId, "usuario_id", user.id(), "limit", limit));
    }
}

package co.medtender.api.ia;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.config.MedtenderProperties;
import co.medtender.api.ingesta.AgenteClient;
import co.medtender.api.limites.Limitador;
import co.medtender.api.security.UsuarioActual;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Consulta de medicamentos de Colombia. A diferencia de la consola RAG no depende de un expediente: se
 * responde solo con la base abierta de INVIMA (datos públicos, sin contenido de clientes). Java exige
 * sesión, limita y audita; el agente interpreta, busca y arma las citas verificables.
 */
@RestController
@RequestMapping("/api/v1/medicamentos")
public class MedicamentoController {

    public record PreguntaIn(@NotBlank @Size(min = 3, max = 1000) String pregunta) {}

    private final AgenteClient agente;
    private final Limitador limitador;
    private final AuditoriaService auditoria;
    private final MedtenderProperties props;

    public MedicamentoController(AgenteClient agente, Limitador limitador, AuditoriaService auditoria,
                                 MedtenderProperties props) {
        this.agente = agente;
        this.limitador = limitador;
        this.auditoria = auditoria;
        this.props = props;
    }

    /** Respuesta con respuestaAnalitica, citas (registros INVIMA, precios regulados) y alertas. */
    @PostMapping("/consultas")
    public JsonNode consultar(@Valid @RequestBody PreguntaIn in, @AuthenticationPrincipal UsuarioActual user) {
        // Cada pregunta cuesta dos llamadas al modelo generativo: mismo límite que la consola RAG.
        var rl = props.rateLimit();
        limitador.exigir("consulta_min", user.id().toString(), rl.consultaUsuarioMin(), 60);
        limitador.exigir("consulta_dia", user.id().toString(), rl.consultaUsuarioDia(), 86400);

        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("tenant_id", user.tenantId());
        cuerpo.put("usuario_id", user.id());
        cuerpo.put("pregunta", in.pregunta());
        JsonNode respuesta = agente.post("/internal/v1/medicamentos/consultas", cuerpo, true);

        // Se audita quién consultó y con qué resultado; nunca el texto de la pregunta.
        Map<String, Object> detalle = new LinkedHashMap<>();
        detalle.put("consulta", respuesta.path("consultaId").asText(null));
        detalle.put("sin_evidencia", respuesta.path("sinEvidencia").asBoolean());
        detalle.put("citas", respuesta.path("citas").size());
        detalle.put("latencia_ms", respuesta.path("latenciaMs").asLong());
        auditoria.auditar(Accion.CONSULTA_MEDICAMENTOS, user, "medicamentos", null, detalle);
        return respuesta;
    }

    /** Qué conjuntos de INVIMA están cargados y desde cuándo. */
    @GetMapping("/fuentes")
    public JsonNode fuentes(@AuthenticationPrincipal UsuarioActual user) {
        return agente.get("/internal/v1/medicamentos/fuentes", Map.of());
    }
}

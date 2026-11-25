package co.medtender.api.ia;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.config.MedtenderProperties;
import co.medtender.api.domain.Permiso;
import co.medtender.api.expediente.AutorizacionExpediente;
import co.medtender.api.ingesta.AgenteClient;
import co.medtender.api.limites.Limitador;
import co.medtender.api.privacidad.ConsentimientoService;
import co.medtender.api.security.UsuarioActual;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * «Preparar mi cita»: resumen de una página con lo reciente, lo que cambió, los medicamentos, diagnósticos y alergias que escriben los
 * documentos y preguntas sugeridas para el médico. Java autoriza (LECTOR), exige consentimiento y correo verificado, limita y audita sin
 * contenido. El PDF lo arma el navegador de la persona: el servidor no genera ni guarda el archivo.
 */
@RestController
@RequestMapping("/api/v1/expedientes/{expedienteId}/preparacion")
public class PreparacionCitaController {

    private final AutorizacionExpediente autorizacion;
    private final AgenteClient agente;
    private final Limitador limitador;
    private final AuditoriaService auditoria;
    private final MedtenderProperties props;
    private final ConsentimientoService consentimiento;

    public PreparacionCitaController(AutorizacionExpediente autorizacion, AgenteClient agente, Limitador limitador,
                                     AuditoriaService auditoria, MedtenderProperties props, ConsentimientoService consentimiento) {
        this.autorizacion = autorizacion;
        this.agente = agente;
        this.limitador = limitador;
        this.auditoria = auditoria;
        this.props = props;
        this.consentimiento = consentimiento;
    }

    @PostMapping
    public JsonNode preparar(@PathVariable UUID expedienteId, @AuthenticationPrincipal UsuarioActual user) {
        autorizacion.obtener(user, expedienteId, Permiso.LECTOR);
        consentimiento.exigir(user);
        // Siempre llama al modelo (las preguntas se proponen de nuevo): cuenta como una consulta.
        var rl = props.rateLimit();
        limitador.exigir("consulta_min", user.id().toString(), rl.consultaUsuarioMin(), 60);
        limitador.exigir("consulta_dia", user.id().toString(), rl.consultaUsuarioDia(), 86400);

        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("tenant_id", user.tenantId());
        cuerpo.put("expediente_id", expedienteId);
        cuerpo.put("usuario_id", user.id());
        JsonNode respuesta = agente.post("/internal/v1/preparaciones", cuerpo, true);

        // Solo ids y conteos: nunca medicamentos, valores, fechas ni el texto de las preguntas.
        Map<String, Object> detalle = new LinkedHashMap<>();
        detalle.put("consulta", respuesta.path("consultaId").asText(null));
        detalle.put("eventos", respuesta.path("eventos").size());
        detalle.put("cambios", respuesta.path("cambios").size());
        detalle.put("medicamentos", respuesta.path("medicamentos").size());
        detalle.put("preguntas", respuesta.path("preguntas").size());
        detalle.put("sin_evidencia", respuesta.path("sinEvidencia").asBoolean());
        detalle.put("latencia_ms", respuesta.path("latenciaMs").asLong());
        auditoria.auditar(Accion.PREPARACION_CITA, user, "expediente", expedienteId, detalle);
        return respuesta;
    }
}

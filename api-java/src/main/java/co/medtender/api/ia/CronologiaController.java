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
import tools.jackson.databind.JsonNode;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Línea de tiempo del expediente y evolución de resultados de laboratorio. Java autoriza (LECTOR), exige el consentimiento y el correo
 * verificado de las cuentas personales, limita y audita; el agente arma la línea con una cita en cada dato, o devuelve la guardada si los
 * documentos no cambiaron (sin llamar al modelo).
 */
@RestController
@RequestMapping("/api/v1/expedientes/{expedienteId}/cronologia")
public class CronologiaController {

    private final AutorizacionExpediente autorizacion;
    private final AgenteClient agente;
    private final Limitador limitador;
    private final AuditoriaService auditoria;
    private final MedtenderProperties props;
    private final ConsentimientoService consentimiento;

    public CronologiaController(AutorizacionExpediente autorizacion, AgenteClient agente, Limitador limitador,
                                AuditoriaService auditoria, MedtenderProperties props, ConsentimientoService consentimiento) {
        this.autorizacion = autorizacion;
        this.agente = agente;
        this.limitador = limitador;
        this.auditoria = auditoria;
        this.props = props;
        this.consentimiento = consentimiento;
    }

    @PostMapping
    public JsonNode armar(@PathVariable UUID expedienteId, @RequestParam(defaultValue = "false") boolean rehacer,
                          @AuthenticationPrincipal UsuarioActual user) {
        UUID tenant = autorizacion.obtenerCompartible(user, expedienteId, Permiso.LECTOR).expediente().getTenantId();
        consentimiento.exigir(user);
        var rl = props.rateLimit();
        String quien = user.id().toString();
        // Rehacerla siempre llama al modelo: cuenta antes, como una consulta.
        if (rehacer) {
            limitador.exigir("consulta_min", quien, rl.consultaUsuarioMin(), 60);
            limitador.exigir("consulta_dia", quien, rl.consultaUsuarioDia(), 86400);
        }

        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("tenant_id", tenant);
        cuerpo.put("expediente_id", expedienteId);
        cuerpo.put("usuario_id", user.id());
        cuerpo.put("rehacer", rehacer);
        JsonNode respuesta = agente.post("/internal/v1/cronologias", cuerpo, true);
        boolean guardada = respuesta.path("guardada").asBoolean(false);
        // Abrir la pestaña devuelve la guardada sin costo; si el agente tuvo que armarla, cuenta como una consulta.
        if (!rehacer && !guardada) {
            limitador.exigir("consulta_min", quien, rl.consultaUsuarioMin(), 60);
            limitador.exigir("consulta_dia", quien, rl.consultaUsuarioDia(), 86400);
        }

        // Solo ids y conteos: nunca fechas, valores ni textos de los documentos.
        Map<String, Object> detalle = new LinkedHashMap<>();
        detalle.put("consulta", respuesta.path("consultaId").asString(null));
        detalle.put("guardada", guardada);
        detalle.put("eventos", respuesta.path("eventos").size());
        detalle.put("examenes", respuesta.path("analitos").size());
        detalle.put("sin_evidencia", respuesta.path("sinEvidencia").asBoolean(false));
        detalle.put("citas", respuesta.path("citas").size());
        detalle.put("latencia_ms", respuesta.path("latenciaMs").asLong(0));
        auditoria.auditar(Accion.LINEA_DE_TIEMPO, user, "expediente", expedienteId, detalle);
        return respuesta;
    }
}

package co.medtender.api.recordatorios;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.config.MedtenderProperties;
import co.medtender.api.domain.Permiso;
import co.medtender.api.domain.Recordatorio;
import co.medtender.api.domain.Recordatorio.Estado;
import co.medtender.api.expediente.AutorizacionExpediente;
import co.medtender.api.ingesta.AgenteClient;
import co.medtender.api.limites.Limitador;
import co.medtender.api.privacidad.ConsentimientoService;
import co.medtender.api.recordatorios.RecordatorioService.RecordatorioOut;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import tools.jackson.databind.JsonNode;
import jakarta.validation.constraints.NotNull;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Recordatorios de controles. «Buscar controles» pide al agente las propuestas de un expediente (con cita); la
 * persona confirma, cambia la fecha, marca como hecho o descarta. Cada recordatorio es solo de quien lo creó.
 */
@RestController
@RequestMapping("/api/v1")
public class RecordatorioController {

    private final AutorizacionExpediente autorizacion;
    private final AgenteClient agente;
    private final RecordatorioService servicio;
    private final Limitador limitador;
    private final AuditoriaService auditoria;
    private final MedtenderProperties props;
    private final ConsentimientoService consentimiento;

    public RecordatorioController(AutorizacionExpediente autorizacion, AgenteClient agente, RecordatorioService servicio,
                                  Limitador limitador, AuditoriaService auditoria, MedtenderProperties props,
                                  ConsentimientoService consentimiento) {
        this.autorizacion = autorizacion;
        this.agente = agente;
        this.servicio = servicio;
        this.limitador = limitador;
        this.auditoria = auditoria;
        this.props = props;
        this.consentimiento = consentimiento;
    }

    public record Cambio(@NotNull Estado estado, LocalDate fecha) {}

    /** Busca los controles que indican los documentos del expediente y guarda las propuestas nuevas. */
    @PostMapping("/expedientes/{expedienteId}/recordatorios/propuestas")
    public List<RecordatorioOut> proponer(@PathVariable UUID expedienteId, @AuthenticationPrincipal UsuarioActual user) {
        autorizacion.obtener(user, expedienteId, Permiso.LECTOR);
        consentimiento.exigir(user);
        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("tenant_id", user.tenantId());
        cuerpo.put("expediente_id", expedienteId);
        cuerpo.put("usuario_id", user.id());
        JsonNode r = agente.post("/internal/v1/recordatorios/propuestas", cuerpo, true);
        // Normalmente reutiliza la línea de tiempo guardada; si el agente tuvo que llamar al modelo, cuenta.
        if (!r.path("lineaGuardada").asBoolean(false)) {
            var rl = props.rateLimit();
            limitador.exigir("consulta_min", user.id().toString(), rl.consultaUsuarioMin(), 60);
            limitador.exigir("consulta_dia", user.id().toString(), rl.consultaUsuarioDia(), 86400);
        }
        int nuevas = servicio.guardarPropuestas(user, expedienteId, r.path("propuestas"));
        auditoria.auditar(Accion.RECORDATORIOS_PROPUESTOS, user, "expediente", expedienteId,
                Map.of("propuestas", r.path("propuestas").size(), "nuevas", nuevas));
        return servicio.listar(user, expedienteId);
    }

    @GetMapping("/recordatorios")
    public List<RecordatorioOut> listar(@RequestParam(required = false) UUID expediente, @AuthenticationPrincipal UsuarioActual user) {
        if (expediente != null) autorizacion.obtener(user, expediente, Permiso.LECTOR);
        return servicio.listar(user, expediente);
    }

    @PatchMapping("/recordatorios/{id}")
    public RecordatorioOut actualizar(@PathVariable UUID id, @RequestBody @jakarta.validation.Valid Cambio cambio,
                                      @AuthenticationPrincipal UsuarioActual user) {
        RecordatorioOut r = servicio.actualizar(user, id, cambio.estado(), cambio.fecha());
        // Sin fechas ni textos: solo el estado.
        auditoria.auditar(Accion.RECORDATORIO_ACTUALIZADO, user, "recordatorio", id, Map.of("estado", r.estado().name()));
        return r;
    }

    private static final DateTimeFormatter ICS_FECHA = DateTimeFormatter.BASIC_ISO_DATE;
    private static final DateTimeFormatter ICS_INSTANTE = DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'").withZone(ZoneOffset.UTC);

    /**
     * Evento de calendario de un recordatorio confirmado. Neutro a propósito: los calendarios se sincronizan con
     * servicios de terceros, así que no lleva el texto del documento ni datos de salud, solo «Control médico».
     */
    @GetMapping("/recordatorios/{id}/calendario.ics")
    public ResponseEntity<byte[]> calendario(@PathVariable UUID id, @AuthenticationPrincipal UsuarioActual user) {
        Recordatorio r = servicio.obtener(user, id);
        if (r.getFecha() == null || r.getEstado() != Estado.CONFIRMADO) {
            throw new ApiException(HttpStatus.CONFLICT, "Confirma el recordatorio con una fecha antes de llevarlo al calendario");
        }
        String ics = String.join("\r\n",
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//MedTender//Recordatorios//ES",
                "CALSCALE:GREGORIAN",
                "METHOD:PUBLISH",
                "BEGIN:VEVENT",
                "UID:" + r.getId() + "@medtender",
                "DTSTAMP:" + ICS_INSTANTE.format(Instant.now()),
                "DTSTART;VALUE=DATE:" + ICS_FECHA.format(r.getFecha()),
                "DTEND;VALUE=DATE:" + ICS_FECHA.format(r.getFecha().plusDays(1)),
                "SUMMARY:Control médico",
                "DESCRIPTION:Recordatorio creado en MedTender. El detalle está en la aplicación.",
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                "DESCRIPTION:Control médico",
                "TRIGGER:-P1D",
                "END:VALARM",
                "END:VEVENT",
                "END:VCALENDAR",
                "");
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType("text/calendar; charset=utf-8"))
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment().filename("control-medico.ics").build().toString())
                .body(ics.getBytes(StandardCharsets.UTF_8));
    }
}

package co.medtender.api.ia;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.config.MedtenderProperties;
import co.medtender.api.domain.DocumentoRepository;
import co.medtender.api.domain.Permiso;
import co.medtender.api.expediente.AutorizacionExpediente;
import co.medtender.api.ingesta.AgenteClient;
import co.medtender.api.limites.Limitador;
import co.medtender.api.privacidad.ConsentimientoService;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import tools.jackson.databind.JsonNode;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * «Explícame este documento». Java autoriza (LECTOR sobre el expediente), exige el consentimiento de las
 * cuentas personales, limita y audita; el agente explica el documento en dos capas con citas verificadas.
 */
@RestController
@RequestMapping("/api/v1/expedientes/{expedienteId}/documentos/{documentoId}/explicacion")
public class ExplicacionController {

    private final AutorizacionExpediente autorizacion;
    private final DocumentoRepository documentos;
    private final AgenteClient agente;
    private final Limitador limitador;
    private final AuditoriaService auditoria;
    private final MedtenderProperties props;
    private final ConsentimientoService consentimiento;

    public ExplicacionController(AutorizacionExpediente autorizacion, DocumentoRepository documentos,
                                 AgenteClient agente, Limitador limitador, AuditoriaService auditoria,
                                 MedtenderProperties props, ConsentimientoService consentimiento) {
        this.autorizacion = autorizacion;
        this.documentos = documentos;
        this.agente = agente;
        this.limitador = limitador;
        this.auditoria = auditoria;
        this.props = props;
        this.consentimiento = consentimiento;
    }

    @PostMapping
    public JsonNode explicar(@PathVariable UUID expedienteId, @PathVariable UUID documentoId,
                             @AuthenticationPrincipal UsuarioActual user) {
        autorizacion.obtener(user, expedienteId, Permiso.LECTOR);
        documentos.findByIdAndExpedienteIdAndTenantId(documentoId, expedienteId, user.tenantId())
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "Documento no encontrado"));
        consentimiento.exigir(user);
        // Cada explicacion cuesta una llamada al modelo generativo, igual que una consulta.
        var rl = props.rateLimit();
        limitador.exigir("consulta_min", user.id().toString(), rl.consultaUsuarioMin(), 60);
        limitador.exigir("consulta_dia", user.id().toString(), rl.consultaUsuarioDia(), 86400);

        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("tenant_id", user.tenantId());
        cuerpo.put("expediente_id", expedienteId);
        cuerpo.put("documento_id", documentoId);
        cuerpo.put("usuario_id", user.id());
        JsonNode respuesta = agente.post("/internal/v1/explicaciones", cuerpo, true);

        // Solo ids y conteos: nunca el contenido del documento ni de la explicacion.
        Map<String, Object> detalle = new LinkedHashMap<>();
        detalle.put("consulta", respuesta.path("consultaId").asString(null));
        detalle.put("documento", documentoId.toString());
        detalle.put("sin_evidencia", respuesta.path("sinEvidencia").asBoolean(false));
        detalle.put("citas", respuesta.path("citas").size());
        detalle.put("latencia_ms", respuesta.path("latenciaMs").asLong(0));
        auditoria.auditar(Accion.EXPLICACION_DOCUMENTO, user, "documento", documentoId, detalle);
        return respuesta;
    }
}

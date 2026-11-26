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
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.security.core.annotation.AuthenticationPrincipal;

/** Re-vectorizacion de un expediente con otro modelo de embeddings, sin volver a subir los PDF (HU4.4). */
@RestController
public class ReindexacionController {

    public record ReindexacionIn(@NotBlank @Size(max = 80) String embeddingModel) {}

    private final AutorizacionExpediente autorizacion;
    private final AgenteClient agente;
    private final Limitador limitador;
    private final AuditoriaService auditoria;
    private final MedtenderProperties props;

    public ReindexacionController(AutorizacionExpediente autorizacion, AgenteClient agente, Limitador limitador,
                                  AuditoriaService auditoria, MedtenderProperties props) {
        this.autorizacion = autorizacion;
        this.agente = agente;
        this.limitador = limitador;
        this.auditoria = auditoria;
        this.props = props;
    }

    @GetMapping("/api/v1/embeddings/modelos")
    public JsonNode modelos() {
        return agente.get("/internal/v1/embeddings/modelos", Map.of());
    }

    /**
     * Recalcula todos los embeddings del expediente con otro modelo a partir del texto guardado en
     * PostgreSQL. Exige permiso ADMIN sobre el expediente.
     */
    @PostMapping("/api/v1/expedientes/{expedienteId}/reindexaciones")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public JsonNode solicitar(@PathVariable UUID expedienteId, @Valid @RequestBody ReindexacionIn in,
                              @AuthenticationPrincipal UsuarioActual user) {
        autorizacion.obtener(user, expedienteId, Permiso.ADMIN);
        limitador.exigir("reindex_usuario", user.id().toString(), props.rateLimit().reindexUsuarioHora(), 3600);

        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("tenant_id", user.tenantId());
        cuerpo.put("expediente_id", expedienteId);
        cuerpo.put("usuario_id", user.id());
        cuerpo.put("embedding_model", in.embeddingModel());
        JsonNode r = agente.post("/internal/v1/reindexaciones", cuerpo, false);

        Map<String, Object> detalle = new LinkedHashMap<>();
        detalle.put("reindexacion", r.path("id").asString(null));
        detalle.put("origen", r.path("modelo_origen").asString(null));
        detalle.put("destino", r.path("modelo_destino").asString(null));
        auditoria.auditar(Accion.REINDEXACION_SOLICITADA, user, "expediente", expedienteId, detalle);
        return r;
    }

    @GetMapping("/api/v1/expedientes/{expedienteId}/reindexaciones")
    public JsonNode listar(@PathVariable UUID expedienteId, @AuthenticationPrincipal UsuarioActual user) {
        autorizacion.obtener(user, expedienteId, Permiso.LECTOR);
        return agente.get("/internal/v1/reindexaciones",
                Map.of("tenant_id", user.tenantId(), "expediente_id", expedienteId));
    }
}

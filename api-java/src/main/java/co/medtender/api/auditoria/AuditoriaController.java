package co.medtender.api.auditoria;

import co.medtender.api.domain.RegistroAuditoria;
import co.medtender.api.domain.RegistroAuditoriaRepository;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.Desplazamiento;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** Consulta del registro de auditoria (solo ADMIN_TENANT, siempre acotada a su tenant). */
@RestController
@RequestMapping("/api/v1/auditoria")
@PreAuthorize("hasRole('ADMIN_TENANT')")
public class AuditoriaController {

    private static final Instant MAXIMO = Instant.parse("9999-12-31T23:59:59Z");

    public record EventoOut(UUID id, Instant createdAt, String accion, String resultado, UUID usuarioId,
                            String email, String recursoTipo, UUID recursoId, String ip, String requestId,
                            Map<String, Object> detalle) {
        static EventoOut de(RegistroAuditoria a) {
            return new EventoOut(a.getId(), a.getCreatedAt(), a.getAccion(), a.getResultado(), a.getUsuarioId(),
                    a.getEmail(), a.getRecursoTipo(), a.getRecursoId(), a.getIp(), a.getRequestId(), a.getDetalle());
        }
    }

    private final RegistroAuditoriaRepository repo;

    public AuditoriaController(RegistroAuditoriaRepository repo) {
        this.repo = repo;
    }

    /**
     * Eventos del tenant, el mas reciente primero. Los intentos de login contra correos que no
     * pertenecen a ningun usuario no tienen tenant y no aparecen aqui (solo en los logs).
     */
    @GetMapping
    public List<EventoOut> listar(@AuthenticationPrincipal UsuarioActual admin,
                                  @RequestParam(required = false) @Size(max = 40) String accion,
                                  @RequestParam(required = false) @Pattern(regexp = "^(OK|DENEGADO|ERROR)$") String resultado,
                                  @RequestParam(name = "usuario_id", required = false) UUID usuarioId,
                                  @RequestParam(name = "recurso_id", required = false) UUID recursoId,
                                  @RequestParam(required = false) Instant desde,
                                  @RequestParam(required = false) Instant hasta,
                                  @RequestParam(defaultValue = "100") @Min(1) @Max(500) int limit,
                                  @RequestParam(defaultValue = "0") @Min(0) int offset) {
        return repo.buscar(admin.tenantId(), accion, resultado, usuarioId, recursoId,
                        desde == null ? Instant.EPOCH : desde, hasta == null ? MAXIMO : hasta,
                        Desplazamiento.de(offset, limit))
                .stream().map(EventoOut::de).toList();
    }
}

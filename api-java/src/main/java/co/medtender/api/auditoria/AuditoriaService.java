package co.medtender.api.auditoria;

import co.medtender.api.domain.RegistroAuditoria;
import co.medtender.api.domain.RegistroAuditoriaRepository;
import co.medtender.api.security.ContextoTenant;
import co.medtender.api.security.UsuarioActual;
import io.micrometer.core.instrument.MeterRegistry;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Registro de auditoria. Cada evento se guarda en su propia transaccion: queda registrado aunque la
 * operacion que lo origino falle o se revierta (p. ej. un acceso denegado). Un fallo al auditar se
 * deja en el log y en una metrica, pero no tumba la peticion del usuario.
 *
 * <p>Nunca se guarda contenido: ni preguntas, ni textos de documentos, ni contrasenas. Solo
 * identificadores, roles, motivos y tamanos.
 */
@Service
public class AuditoriaService {

    private static final Logger log = LoggerFactory.getLogger(AuditoriaService.class);

    private final RegistroAuditoriaRepository repo;
    private final TransactionTemplate tx;
    private final MeterRegistry metricas;

    public AuditoriaService(RegistroAuditoriaRepository repo, PlatformTransactionManager tm, MeterRegistry metricas) {
        this.repo = repo;
        this.metricas = metricas;
        this.tx = new TransactionTemplate(tm);
        this.tx.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
    }

    /** Evento realizado por un usuario autenticado. */
    public void auditar(Accion accion, UsuarioActual usuario, String recursoTipo, UUID recursoId,
                        Map<String, Object> detalle) {
        var contexto = ContextoTenant.actual();
        // Un cuidador actua en el expediente de otra persona: el evento es del registro de ella.
        UUID tenant = contexto.expedienteInvitado() != null ? contexto.tenantId() : usuario.tenantId();
        guardar(accion, tenant, usuario.id(), usuario.email(), "OK", recursoTipo, recursoId, detalle);
    }

    /** Evento con identidad parcial o sin ella (login fallido, registro, acceso denegado...). */
    public void auditar(Accion accion, UUID tenantId, UUID usuarioId, String email, String resultado,
                        String recursoTipo, UUID recursoId, Map<String, Object> detalle) {
        guardar(accion, tenantId, usuarioId, email, resultado, recursoTipo, recursoId, detalle);
    }

    private void guardar(Accion accion, UUID tenantId, UUID usuarioId, String email, String resultado,
                         String recursoTipo, UUID recursoId, Map<String, Object> detalle) {
        try {
            String correo = email == null || email.isEmpty() ? null : email.substring(0, Math.min(150, email.length()));
            var registro = new RegistroAuditoria(tenantId, usuarioId, correo, accion.name(), resultado,
                    recursoTipo, recursoId, MDC.get("ip"), MDC.get("request_id"),
                    detalle == null ? Map.of() : detalle);
            // Se escribe como proceso del sistema: a que cuenta pertenece el evento lo decide este codigo, no el
            // contexto de la peticion. Sin esto se perdian en silencio los eventos de endpoints sin sesion (cerrar
            // sesion, confirmar el correo) y los del registro de otra cuenta (un cuidador).
            ContextoTenant.comoSistema(() -> tx.executeWithoutResult(s -> repo.save(registro)));
        } catch (RuntimeException e) {
            metricas.counter("medtender_auditoria_fallos_total").increment();
            log.error("No se pudo registrar el evento de auditoria {}", accion, e);
        }
    }
}

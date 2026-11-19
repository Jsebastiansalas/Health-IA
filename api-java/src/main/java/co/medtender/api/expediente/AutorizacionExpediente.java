package co.medtender.api.expediente;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.domain.Expediente;
import co.medtender.api.domain.ExpedientePermisoRepository;
import co.medtender.api.domain.ExpedienteRepository;
import co.medtender.api.domain.Permiso;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

/**
 * Autorizacion por expediente. Toda lectura o escritura de un expediente debe pasar por aqui.
 *
 * <ul>
 *   <li>El expediente siempre se busca filtrando por el tenant del usuario: otro tenant => 404.
 *   <li>ADMIN_TENANT tiene nivel ADMIN sobre todos los expedientes de su tenant.
 *   <li>Los demas necesitan una fila en expediente_permisos. Sin fila => 404 (no revela
 *       existencia); con nivel insuficiente => 403.
 * </ul>
 */
@Service
public class AutorizacionExpediente {

    public record Autorizado(Expediente expediente, Permiso permiso) {}

    private final ExpedienteRepository expedientes;
    private final ExpedientePermisoRepository permisos;
    private final AuditoriaService auditoria;

    public AutorizacionExpediente(ExpedienteRepository expedientes, ExpedientePermisoRepository permisos,
                                  AuditoriaService auditoria) {
        this.expedientes = expedientes;
        this.permisos = permisos;
        this.auditoria = auditoria;
    }

    public Optional<Permiso> permisoEfectivo(UsuarioActual u, UUID expedienteId) {
        if (u.esAdminTenant()) {
            return Optional.of(Permiso.ADMIN);
        }
        return permisos.findByTenantIdAndExpedienteIdAndUsuarioId(u.tenantId(), expedienteId, u.id())
                .map(p -> p.getPermiso());
    }

    public Autorizado obtener(UsuarioActual u, UUID expedienteId, Permiso minimo) {
        var noEncontrado = new ApiException(HttpStatus.NOT_FOUND, "Expediente no encontrado");
        Expediente e = expedientes.findByIdAndTenantId(expedienteId, u.tenantId()).orElse(null);
        if (e == null) {
            // Inexistente o de otro tenant: la respuesta es identica, pero queda registrado.
            denegar(u, expedienteId, Map.of("motivo", "inexistente_o_otro_tenant"));
            throw noEncontrado;
        }
        Permiso permiso = permisoEfectivo(u, expedienteId).orElse(null);
        if (permiso == null) {
            denegar(u, expedienteId, Map.of("motivo", "sin_permiso"));
            throw noEncontrado;
        }
        if (permiso.nivel() < minimo.nivel()) {
            denegar(u, expedienteId, Map.of("motivo", "permiso_insuficiente", "requerido", minimo.name(),
                    "tiene", permiso.name()));
            throw new ApiException(HttpStatus.FORBIDDEN, "Se requiere permiso " + minimo.name());
        }
        return new Autorizado(e, permiso);
    }

    private void denegar(UsuarioActual u, UUID expedienteId, Map<String, Object> detalle) {
        auditoria.auditar(Accion.ACCESO_DENEGADO, u.tenantId(), u.id(), u.email(), "DENEGADO", "expediente",
                expedienteId, detalle);
    }
}

package co.medtender.api.privacidad;

import co.medtender.api.domain.TenantRepository;
import co.medtender.api.domain.TipoTenant;
import co.medtender.api.ingesta.AlmacenEfimero;
import co.medtender.api.web.ApiException;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Derecho de supresion: la persona puede borrar el historial de preguntas de un expediente y eliminar
 * su cuenta con todo lo que contiene. El registro de auditoria no se toca (es de solo anexado y no guarda
 * contenido: solo identificadores).
 */
@Service
public class PrivacidadService {

    private final JdbcTemplate jdbc;
    private final TenantRepository tenants;
    private final AlmacenEfimero almacen;

    public PrivacidadService(JdbcTemplate jdbc, TenantRepository tenants, AlmacenEfimero almacen) {
        this.jdbc = jdbc;
        this.tenants = tenants;
        this.almacen = almacen;
    }

    /** Borra preguntas y respuestas guardadas de un expediente. Devuelve cuantas eran. */
    @Transactional
    public int borrarHistorial(UUID tenantId, UUID expedienteId) {
        return jdbc.update("DELETE FROM consultas WHERE tenant_id = ? AND expediente_id = ?", tenantId, expedienteId);
    }

    /**
     * Elimina la cuenta personal completa: expedientes (y en cascada documentos, fragmentos, permisos,
     * consultas y reindexaciones), actas de purga, consentimientos, el usuario y el tenant. Ningun PDF
     * temporal sobrevive. Las organizaciones no usan esta via.
     */
    @Transactional
    public void eliminarCuentaPersonal(UUID tenantId) {
        var tenant = tenants.findById(tenantId).orElseThrow();
        if (tenant.getTipo() != TipoTenant.PERSONAL) {
            throw new ApiException(HttpStatus.FORBIDDEN, "Solo las cuentas personales se eliminan de esta forma");
        }
        List<UUID> pendientes = jdbc.queryForList(
                "SELECT id FROM documentos WHERE tenant_id = ? AND temp_file_purged = false", UUID.class, tenantId);
        pendientes.forEach(almacen::borrarTodo);
        jdbc.update("DELETE FROM expedientes WHERE tenant_id = ?", tenantId);
        jdbc.update("DELETE FROM actas_purga WHERE tenant_id = ?", tenantId);
        jdbc.update("DELETE FROM consentimientos WHERE tenant_id = ?", tenantId);
        jdbc.update("DELETE FROM usuarios WHERE tenant_id = ?", tenantId);
        jdbc.update("DELETE FROM tenants WHERE id = ?", tenantId);
    }
}

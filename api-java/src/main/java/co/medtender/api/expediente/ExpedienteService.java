package co.medtender.api.expediente;

import co.medtender.api.config.IngestaProperties;
import co.medtender.api.domain.DocumentoRepository;
import co.medtender.api.domain.Expediente;
import co.medtender.api.domain.ExpedientePermiso;
import co.medtender.api.domain.ExpedientePermisoRepository;
import co.medtender.api.domain.ExpedienteRepository;
import co.medtender.api.domain.Permiso;
import co.medtender.api.domain.TipoExpediente;
import co.medtender.api.ingesta.AlmacenEfimero;
import co.medtender.api.web.ApiException;
import java.util.UUID;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Escrituras sobre expedientes y sus permisos (cada metodo es una transaccion). */
@Service
public class ExpedienteService {

    private final ExpedienteRepository expedientes;
    private final ExpedientePermisoRepository permisos;
    private final DocumentoRepository documentos;
    private final AlmacenEfimero almacen;
    private final IngestaProperties ingesta;

    public ExpedienteService(ExpedienteRepository expedientes, ExpedientePermisoRepository permisos,
                             DocumentoRepository documentos, AlmacenEfimero almacen, IngestaProperties ingesta) {
        this.expedientes = expedientes;
        this.permisos = permisos;
        this.documentos = documentos;
        this.almacen = almacen;
        this.ingesta = ingesta;
    }

    @Transactional
    public Expediente crear(UUID tenantId, UUID creadorId, String codigo, String titulo, String entidad,
                            TipoExpediente tipo) {
        String modelo = ingesta.embeddingModelDefault();
        try {
            Expediente e = expedientes.saveAndFlush(new Expediente(tenantId, codigo, titulo, entidad, tipo, modelo,
                    IngestaProperties.dimensionDe(modelo), creadorId));
            // El creador queda como ADMIN del expediente.
            permisos.saveAndFlush(new ExpedientePermiso(tenantId, e.getId(), creadorId, Permiso.ADMIN));
            return e;
        } catch (DataIntegrityViolationException ex) {
            throw new ApiException(HttpStatus.CONFLICT, "Ya existe un expediente con ese código");
        }
    }

    @Transactional
    public Expediente actualizar(UUID tenantId, UUID id, ExpedienteDtos.ExpedienteUpdate in) {
        Expediente e = expedientes.findByIdAndTenantId(id, tenantId).orElseThrow();
        if (in.titulo() != null) e.setTitulo(in.titulo());
        if (in.entidadContratante() != null) e.setEntidadContratante(in.entidadContratante());
        if (in.tipoExpediente() != null) e.setTipoExpediente(in.tipoExpediente());
        if (in.estado() != null) e.setEstado(in.estado());
        return e;
    }

    /** Borra el expediente (la base elimina en cascada documentos, fragmentos y permisos). */
    @Transactional
    public String eliminar(UUID tenantId, UUID id) {
        Expediente e = expedientes.findByIdAndTenantId(id, tenantId).orElseThrow();
        // Ningun PDF temporal debe sobrevivir al expediente al que pertenecia.
        documentos.findByExpedienteIdAndTempFilePurgedFalse(id).forEach(d -> almacen.borrarTodo(d.getId()));
        String codigo = e.getCodigoExpediente();
        expedientes.delete(e);
        return codigo;
    }

    @Transactional
    public ExpedientePermiso asignarPermiso(UUID tenantId, UUID expedienteId, UUID usuarioId, Permiso permiso) {
        var existente = permisos.findByExpedienteIdAndUsuarioId(expedienteId, usuarioId).orElse(null);
        if (existente == null) {
            return permisos.saveAndFlush(new ExpedientePermiso(tenantId, expedienteId, usuarioId, permiso));
        }
        if (existente.getPermiso() == Permiso.ADMIN && permiso != Permiso.ADMIN) {
            asegurarOtroAdmin(expedienteId, usuarioId);
        }
        existente.setPermiso(permiso);
        return existente;
    }

    /** Devuelve el permiso que tenia el usuario. */
    @Transactional
    public Permiso revocarPermiso(UUID tenantId, UUID expedienteId, UUID usuarioId) {
        var existente = permisos.findByTenantIdAndExpedienteIdAndUsuarioId(tenantId, expedienteId, usuarioId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "Permiso no encontrado"));
        if (existente.getPermiso() == Permiso.ADMIN) {
            asegurarOtroAdmin(expedienteId, usuarioId);
        }
        Permiso previo = existente.getPermiso();
        permisos.delete(existente);
        return previo;
    }

    /** Impide dejar un expediente sin ningun permiso ADMIN explicito. */
    private void asegurarOtroAdmin(UUID expedienteId, UUID usuarioId) {
        if (permisos.countByExpedienteIdAndPermisoAndUsuarioIdNot(expedienteId, Permiso.ADMIN, usuarioId) == 0) {
            throw new ApiException(HttpStatus.CONFLICT, "El expediente debe conservar al menos un ADMIN");
        }
    }
}

package co.medtender.api.expediente;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.domain.Permiso;
import co.medtender.api.domain.RolGlobal;
import co.medtender.api.domain.UsuarioRepository;
import co.medtender.api.domain.ExpedientePermisoRepository;
import co.medtender.api.domain.ExpedienteRepository;
import co.medtender.api.expediente.ExpedienteDtos.ExpedienteCreate;
import co.medtender.api.expediente.ExpedienteDtos.ExpedienteOut;
import co.medtender.api.expediente.ExpedienteDtos.ExpedienteUpdate;
import co.medtender.api.expediente.ExpedienteDtos.PermisoIn;
import co.medtender.api.expediente.ExpedienteDtos.PermisoOut;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import co.medtender.api.web.Desplazamiento;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.Comparator;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/expedientes")
public class ExpedienteController {

    /** Roles que pueden crear expedientes nuevos. */
    private static final Set<RolGlobal> ROLES_CREADORES = EnumSet.of(RolGlobal.ADMIN_TENANT, RolGlobal.JURIDICO,
            RolGlobal.AUDITOR_MEDICO, RolGlobal.BIOMEDICO);

    private final ExpedienteRepository expedientes;
    private final ExpedientePermisoRepository permisos;
    private final UsuarioRepository usuarios;
    private final ExpedienteService servicio;
    private final AutorizacionExpediente autorizacion;
    private final AuditoriaService auditoria;
    private final co.medtender.api.compartir.ComparticionService comparticiones;

    public ExpedienteController(ExpedienteRepository expedientes, ExpedientePermisoRepository permisos,
                                UsuarioRepository usuarios, ExpedienteService servicio,
                                AutorizacionExpediente autorizacion, AuditoriaService auditoria,
                                co.medtender.api.compartir.ComparticionService comparticiones) {
        this.comparticiones = comparticiones;
        this.expedientes = expedientes;
        this.permisos = permisos;
        this.usuarios = usuarios;
        this.servicio = servicio;
        this.autorizacion = autorizacion;
        this.auditoria = auditoria;
    }

    @GetMapping
    public List<ExpedienteOut> listar(@AuthenticationPrincipal UsuarioActual user,
                                      @RequestParam(defaultValue = "50") @Min(1) @Max(200) int limit,
                                      @RequestParam(defaultValue = "0") @Min(0) int offset) {
        var pagina = Desplazamiento.de(offset, limit);
        if (user.esAdminTenant()) {
            return expedientes.findByTenantIdOrderByCreatedAtDesc(user.tenantId(), pagina).stream()
                    .map(e -> ExpedienteOut.de(e, Permiso.ADMIN)).toList();
        }
        return expedientes.visiblesPara(user.tenantId(), user.id(), pagina).stream()
                .map(c -> ExpedienteOut.de(c.expediente(), c.permiso())).toList();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ExpedienteOut crear(@Valid @RequestBody ExpedienteCreate in, @AuthenticationPrincipal UsuarioActual user) {
        if (!ROLES_CREADORES.contains(user.rol())) {
            throw new ApiException(HttpStatus.FORBIDDEN, "Tu rol no puede crear expedientes");
        }
        var e = servicio.crear(user.tenantId(), user.id(), in.codigoExpediente(), in.titulo(),
                in.entidadContratante(), in.tipoExpediente());
        auditoria.auditar(Accion.EXPEDIENTE_CREADO, user, "expediente", e.getId(),
                Map.of("codigo", e.getCodigoExpediente()));
        return ExpedienteOut.de(e, Permiso.ADMIN);
    }

    @GetMapping("/{expedienteId}")
    public ExpedienteOut obtener(@PathVariable UUID expedienteId, @AuthenticationPrincipal UsuarioActual user) {
        var a = autorizacion.obtenerCompartible(user, expedienteId, Permiso.LECTOR);
        return ExpedienteOut.de(a.expediente(), a.permiso(),
                a.invitado() ? comparticiones.quienComparte(user, expedienteId) : null);
    }

    @PatchMapping("/{expedienteId}")
    public ExpedienteOut actualizar(@PathVariable UUID expedienteId, @Valid @RequestBody ExpedienteUpdate in,
                                    @AuthenticationPrincipal UsuarioActual user) {
        var a = autorizacion.obtener(user, expedienteId, Permiso.EDITOR);
        var e = servicio.actualizar(user.tenantId(), expedienteId, in);
        var campos = new TreeSet<String>();
        if (in.titulo() != null) campos.add("titulo");
        if (in.entidadContratante() != null) campos.add("entidad_contratante");
        if (in.tipoExpediente() != null) campos.add("tipo_expediente");
        if (in.estado() != null) campos.add("estado");
        auditoria.auditar(Accion.EXPEDIENTE_ACTUALIZADO, user, "expediente", e.getId(), Map.of("campos", campos));
        return ExpedienteOut.de(e, a.permiso());
    }

    @DeleteMapping("/{expedienteId}")
    public ResponseEntity<Void> eliminar(@PathVariable UUID expedienteId, @AuthenticationPrincipal UsuarioActual user) {
        autorizacion.obtener(user, expedienteId, Permiso.ADMIN);
        String codigo = servicio.eliminar(user.tenantId(), expedienteId);
        auditoria.auditar(Accion.EXPEDIENTE_ELIMINADO, user, "expediente", expedienteId, Map.of("codigo", codigo));
        return ResponseEntity.noContent().build();
    }

    // ---------- Permisos por expediente ----------

    @GetMapping("/{expedienteId}/permisos")
    public List<PermisoOut> listarPermisos(@PathVariable UUID expedienteId, @AuthenticationPrincipal UsuarioActual user) {
        autorizacion.obtener(user, expedienteId, Permiso.ADMIN);
        return permisos.findByTenantIdAndExpedienteId(user.tenantId(), expedienteId).stream()
                .map(p -> {
                    var u = usuarios.findById(p.getUsuarioId()).orElseThrow();
                    return new PermisoOut(u.getId(), u.getEmail(), u.getNombreCompleto(), p.getPermiso());
                })
                .sorted(Comparator.comparing(PermisoOut::email))
                .toList();
    }

    @PutMapping("/{expedienteId}/permisos/{usuarioId}")
    public PermisoOut asignarPermiso(@PathVariable UUID expedienteId, @PathVariable UUID usuarioId,
                                     @Valid @RequestBody PermisoIn in, @AuthenticationPrincipal UsuarioActual user) {
        autorizacion.obtener(user, expedienteId, Permiso.ADMIN);
        // Un usuario de otro tenant se trata como inexistente.
        var destino = usuarios.findByIdAndTenantId(usuarioId, user.tenantId())
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "Usuario no encontrado"));
        servicio.asignarPermiso(user.tenantId(), expedienteId, usuarioId, in.permiso());
        auditoria.auditar(Accion.PERMISO_ASIGNADO, user, "expediente", expedienteId,
                Map.of("destinatario", destino.getId().toString(), "permiso", in.permiso().name()));
        return new PermisoOut(destino.getId(), destino.getEmail(), destino.getNombreCompleto(), in.permiso());
    }

    @DeleteMapping("/{expedienteId}/permisos/{usuarioId}")
    public ResponseEntity<Void> revocarPermiso(@PathVariable UUID expedienteId, @PathVariable UUID usuarioId,
                                               @AuthenticationPrincipal UsuarioActual user) {
        autorizacion.obtener(user, expedienteId, Permiso.ADMIN);
        Permiso previo = servicio.revocarPermiso(user.tenantId(), expedienteId, usuarioId);
        auditoria.auditar(Accion.PERMISO_REVOCADO, user, "expediente", expedienteId,
                Map.of("destinatario", usuarioId.toString(), "permiso_previo", previo.name()));
        return ResponseEntity.noContent().build();
    }
}

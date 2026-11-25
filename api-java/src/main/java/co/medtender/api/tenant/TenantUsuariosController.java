package co.medtender.api.tenant;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.auth.Dtos.TenantOut;
import co.medtender.api.auth.Dtos.TenantUpdate;
import co.medtender.api.auth.Dtos.UsuarioCreate;
import co.medtender.api.auth.Dtos.UsuarioOut;
import co.medtender.api.auth.Dtos.UsuarioUpdate;
import co.medtender.api.auth.IdentidadService;
import co.medtender.api.domain.TenantRepository;
import co.medtender.api.domain.UsuarioRepository;
import co.medtender.api.security.PasswordService;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import co.medtender.api.web.Desplazamiento;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeSet;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/** Administracion del tenant y sus usuarios (solo ADMIN_TENANT). */
@RestController
@RequestMapping("/api/v1")
@PreAuthorize("hasRole('ADMIN_TENANT')")
public class TenantUsuariosController {

    private final TenantRepository tenants;
    private final UsuarioRepository usuarios;
    private final IdentidadService identidad;
    private final PasswordService passwords;
    private final AuditoriaService auditoria;
    private final co.medtender.api.auth.PoliticaContrasena politica;

    public TenantUsuariosController(TenantRepository tenants, UsuarioRepository usuarios, IdentidadService identidad,
                                    PasswordService passwords, AuditoriaService auditoria,
                                    co.medtender.api.auth.PoliticaContrasena politica) {
        this.politica = politica;
        this.tenants = tenants;
        this.usuarios = usuarios;
        this.identidad = identidad;
        this.passwords = passwords;
        this.auditoria = auditoria;
    }

    @GetMapping("/tenant")
    public TenantOut obtenerTenant(@AuthenticationPrincipal UsuarioActual admin) {
        return TenantOut.de(tenants.findById(admin.tenantId()).orElseThrow());
    }

    @PatchMapping("/tenant")
    public TenantOut actualizarTenant(@Valid @RequestBody TenantUpdate in, @AuthenticationPrincipal UsuarioActual admin) {
        var t = identidad.actualizarTenant(admin.tenantId(), in.nombre(), in.politicaBorrado());
        var campos = new TreeSet<String>();
        if (in.nombre() != null) campos.add("nombre");
        if (in.politicaBorrado() != null) campos.add("politica_borrado");
        auditoria.auditar(Accion.TENANT_ACTUALIZADO, admin, "tenant", t.getId(), Map.of("campos", campos));
        return TenantOut.de(t);
    }

    @GetMapping("/usuarios")
    public List<UsuarioOut> listar(@AuthenticationPrincipal UsuarioActual admin,
                                   @RequestParam(defaultValue = "50") @Min(1) @Max(200) int limit,
                                   @RequestParam(defaultValue = "0") @Min(0) int offset) {
        return usuarios.findByTenantIdOrderByCreatedAt(admin.tenantId(), Desplazamiento.de(offset, limit))
                .stream().map(UsuarioOut::de).toList();
    }

    @PostMapping("/usuarios")
    @ResponseStatus(HttpStatus.CREATED)
    public UsuarioOut crear(@Valid @RequestBody UsuarioCreate in, @AuthenticationPrincipal UsuarioActual admin) {
        politica.exigir(in.password(), in.email(), in.nombreCompleto());
        String hash = passwords.hash(in.password());
        var u = identidad.crearUsuario(admin.tenantId(), in.email().toLowerCase(Locale.ROOT), hash,
                in.nombreCompleto(), in.rolGlobal());
        auditoria.auditar(Accion.USUARIO_CREADO, admin, "usuario", u.getId(), Map.of("rol", u.getRolGlobal().name()));
        return UsuarioOut.de(u);
    }

    @PatchMapping("/usuarios/{usuarioId}")
    public UsuarioOut actualizar(@PathVariable UUID usuarioId, @Valid @RequestBody UsuarioUpdate in,
                                 @AuthenticationPrincipal UsuarioActual admin) {
        var c = identidad.actualizarUsuario(admin.tenantId(), admin.id(), usuarioId, in);
        var u = c.usuario();
        var campos = new TreeSet<String>();
        if (in.nombreCompleto() != null) campos.add("nombre_completo");
        if (in.rolGlobal() != null) campos.add("rol_global");
        if (in.activo() != null) campos.add("activo");
        auditoria.auditar(Accion.USUARIO_ACTUALIZADO, admin, "usuario", u.getId(), Map.of(
                "antes", Map.of("rol", c.rolAntes().name(), "activo", c.activoAntes()),
                "despues", Map.of("rol", u.getRolGlobal().name(), "activo", u.isActivo()),
                "campos", campos));
        return UsuarioOut.de(u);
    }
}

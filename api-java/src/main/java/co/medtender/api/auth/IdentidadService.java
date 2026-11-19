package co.medtender.api.auth;

import co.medtender.api.domain.PoliticaBorrado;
import co.medtender.api.domain.RolGlobal;
import co.medtender.api.domain.Tenant;
import co.medtender.api.domain.TenantRepository;
import co.medtender.api.domain.Usuario;
import co.medtender.api.domain.UsuarioRepository;
import co.medtender.api.web.ApiException;
import java.util.UUID;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Operaciones de escritura sobre tenants y usuarios. Los hashes de contrasena llegan ya calculados. */
@Service
public class IdentidadService {

    private final TenantRepository tenants;
    private final UsuarioRepository usuarios;

    public IdentidadService(TenantRepository tenants, UsuarioRepository usuarios) {
        this.tenants = tenants;
        this.usuarios = usuarios;
    }

    public record TenantConAdmin(Tenant tenant, Usuario admin) {}

    @Transactional
    public TenantConAdmin registrarTenant(String nombre, String nit, PoliticaBorrado politica, String email,
                                          String passwordHash, String nombreAdmin) {
        try {
            Tenant t = tenants.saveAndFlush(new Tenant(nombre, nit, politica == null ? PoliticaBorrado.INMEDIATO : politica));
            Usuario admin = usuarios.saveAndFlush(
                    new Usuario(t.getId(), email, passwordHash, nombreAdmin, RolGlobal.ADMIN_TENANT));
            return new TenantConAdmin(t, admin);
        } catch (DataIntegrityViolationException e) {
            throw new ApiException(HttpStatus.CONFLICT, "El NIT o el email ya están registrados");
        }
    }

    @Transactional
    public Usuario crearUsuario(UUID tenantId, String email, String passwordHash, String nombre, RolGlobal rol) {
        try {
            return usuarios.saveAndFlush(new Usuario(tenantId, email, passwordHash, nombre, rol));
        } catch (DataIntegrityViolationException e) {
            throw new ApiException(HttpStatus.CONFLICT, "El email ya está registrado");
        }
    }

    @Transactional
    public Tenant actualizarTenant(UUID tenantId, String nombre, PoliticaBorrado politica) {
        Tenant t = tenants.findById(tenantId).orElseThrow();
        if (nombre != null) {
            t.setNombre(nombre);
        }
        if (politica != null) {
            t.setPoliticaBorrado(politica);
        }
        return t;
    }

    /** Resultado con los valores previos, para auditar el cambio. */
    public record Cambio(Usuario usuario, RolGlobal rolAntes, boolean activoAntes) {}

    @Transactional
    public Cambio actualizarUsuario(UUID tenantId, UUID actorId, UUID usuarioId, Dtos.UsuarioUpdate datos) {
        // Siempre acotado al tenant del administrador: un id de otro tenant es "no encontrado".
        Usuario u = usuarios.findByIdAndTenantId(usuarioId, tenantId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "Usuario no encontrado"));
        boolean pierdeAdmin = Boolean.FALSE.equals(datos.activo())
                || (datos.rolGlobal() != null && datos.rolGlobal() != RolGlobal.ADMIN_TENANT);
        if (u.getId().equals(actorId) && pierdeAdmin) {
            throw new ApiException(HttpStatus.CONFLICT,
                    "No puedes desactivarte ni quitarte el rol de administrador");
        }
        var cambio = new Cambio(u, u.getRolGlobal(), u.isActivo());
        if (datos.nombreCompleto() != null) {
            u.setNombreCompleto(datos.nombreCompleto());
        }
        if (datos.rolGlobal() != null) {
            u.setRolGlobal(datos.rolGlobal());
        }
        if (datos.activo() != null) {
            u.setActivo(datos.activo());
        }
        return cambio;
    }
}

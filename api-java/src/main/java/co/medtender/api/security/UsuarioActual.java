package co.medtender.api.security;

import co.medtender.api.domain.RolGlobal;
import java.util.UUID;

/** Identidad autenticada de la peticion, releida de la base de datos en cada solicitud. */
public record UsuarioActual(UUID id, UUID tenantId, RolGlobal rol, String email) {

    public boolean esAdminTenant() {
        return rol == RolGlobal.ADMIN_TENANT;
    }
}

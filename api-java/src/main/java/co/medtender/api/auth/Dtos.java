package co.medtender.api.auth;

import co.medtender.api.domain.PoliticaBorrado;
import co.medtender.api.domain.RolGlobal;
import co.medtender.api.domain.Tenant;
import co.medtender.api.domain.Usuario;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.UUID;

/** Contratos JSON (snake_case por configuracion global de Jackson). */
public final class Dtos {

    private Dtos() {}

    public record LoginIn(@NotBlank @Email @Size(max = 150) String email, @NotBlank String password) {}

    public record RefreshIn(@NotBlank String refreshToken) {}

    public record RegistroTenantIn(
            @NotBlank @Size(min = 2, max = 150) String tenantNombre,
            @NotBlank @Size(min = 3, max = 50) String nit,
            PoliticaBorrado politicaBorrado,
            @NotBlank @Email @Size(max = 150) String adminEmail,
            @NotBlank @Size(min = 10) String adminPassword,
            @NotBlank @Size(min = 2, max = 150) String adminNombre) {}

    public record RegistroPersonalIn(
            @NotBlank @Size(min = 2, max = 150) String nombre,
            @NotBlank @Email @Size(max = 150) String email,
            @NotBlank @Size(min = 10) String password) {}

    public record TokensOut(String accessToken, String refreshToken, String tokenType) {
        public static TokensOut de(String access, String refresh) {
            return new TokensOut(access, refresh, "bearer");
        }
    }

    /** Respuesta del ingreso: los tokens o, si la cuenta tiene verificación en dos pasos, el desafío. */
    public record LoginOut(String accessToken, String refreshToken, String tokenType, boolean requiere2fa, String desafio) {
        public static LoginOut de(TokensOut t) {
            return new LoginOut(t.accessToken(), t.refreshToken(), t.tokenType(), false, null);
        }

        public static LoginOut dosPasos(String desafio) {
            return new LoginOut(null, null, null, true, desafio);
        }
    }

    public record UsuarioOut(UUID id, UUID tenantId, String email, String nombreCompleto, RolGlobal rolGlobal,
                             boolean activo, Instant createdAt, boolean dosPasos) {
        public static UsuarioOut de(Usuario u) {
            return new UsuarioOut(u.getId(), u.getTenantId(), u.getEmail(), u.getNombreCompleto(),
                    u.getRolGlobal(), u.isActivo(), u.getCreatedAt(), u.isTotpActivo());
        }
    }

    public record UsuarioCreate(
            @NotBlank @Email @Size(max = 150) String email,
            @NotBlank @Size(min = 10) String password,
            @NotBlank @Size(min = 2, max = 150) String nombreCompleto,
            @NotNull RolGlobal rolGlobal) {}

    public record UsuarioUpdate(@Size(min = 2, max = 150) String nombreCompleto, RolGlobal rolGlobal,
                                Boolean activo) {}

    public record TenantOut(UUID id, String nombre, String nit, PoliticaBorrado politicaBorrado, Instant createdAt) {
        public static TenantOut de(Tenant t) {
            return new TenantOut(t.getId(), t.getNombre(), t.getNit(), t.getPoliticaBorrado(), t.getCreatedAt());
        }
    }

    public record TenantUpdate(@Size(min = 2, max = 150) String nombre, PoliticaBorrado politicaBorrado) {}
}

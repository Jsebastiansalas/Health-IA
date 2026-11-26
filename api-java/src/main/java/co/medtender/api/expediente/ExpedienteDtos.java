package co.medtender.api.expediente;

import co.medtender.api.domain.EstadoExpediente;
import co.medtender.api.domain.Expediente;
import co.medtender.api.domain.Permiso;
import co.medtender.api.domain.TipoExpediente;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.UUID;

public final class ExpedienteDtos {

    private ExpedienteDtos() {}

    public record ExpedienteCreate(
            @NotBlank @Size(max = 80) String codigoExpediente,
            @NotBlank @Size(max = 250) String titulo,
            @Size(max = 200) String entidadContratante,
            @NotNull TipoExpediente tipoExpediente) {}

    /** Campos ausentes (null) no se modifican. */
    public record ExpedienteUpdate(
            @Size(min = 1, max = 250) String titulo,
            @Size(max = 200) String entidadContratante,
            TipoExpediente tipoExpediente,
            EstadoExpediente estado) {}

    public record ExpedienteOut(UUID id, UUID tenantId, String codigoExpediente, String titulo,
                                String entidadContratante, TipoExpediente tipoExpediente, EstadoExpediente estado,
                                String embeddingModelActivo, int embeddingDimension, UUID createdBy,
                                Instant createdAt, Permiso miPermiso, String compartidoPor) {
        public static ExpedienteOut de(Expediente e, Permiso permiso) {
            return de(e, permiso, null);
        }

        public static ExpedienteOut de(Expediente e, Permiso permiso, String compartidoPor) {
            return new ExpedienteOut(e.getId(), e.getTenantId(), e.getCodigoExpediente(), e.getTitulo(),
                    e.getEntidadContratante(), e.getTipoExpediente(), e.getEstado(), e.getEmbeddingModelActivo(),
                    e.getEmbeddingDimension(), e.getCreatedBy(), e.getCreatedAt(), permiso, compartidoPor);
        }
    }

    public record PermisoIn(@NotNull Permiso permiso) {}

    public record PermisoOut(UUID usuarioId, String email, String nombreCompleto, Permiso permiso) {}
}

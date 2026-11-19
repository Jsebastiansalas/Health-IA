package co.medtender.api.domain;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ExpedientePermisoRepository extends JpaRepository<ExpedientePermiso, UUID> {

    Optional<ExpedientePermiso> findByTenantIdAndExpedienteIdAndUsuarioId(UUID tenantId, UUID expedienteId, UUID usuarioId);

    Optional<ExpedientePermiso> findByExpedienteIdAndUsuarioId(UUID expedienteId, UUID usuarioId);

    List<ExpedientePermiso> findByTenantIdAndExpedienteId(UUID tenantId, UUID expedienteId);

    long countByExpedienteIdAndPermisoAndUsuarioIdNot(UUID expedienteId, Permiso permiso, UUID usuarioId);
}

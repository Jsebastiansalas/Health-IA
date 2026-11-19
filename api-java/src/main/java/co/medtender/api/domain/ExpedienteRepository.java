package co.medtender.api.domain;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ExpedienteRepository extends JpaRepository<Expediente, UUID> {

    Optional<Expediente> findByIdAndTenantId(UUID id, UUID tenantId);

    List<Expediente> findByTenantIdOrderByCreatedAtDesc(UUID tenantId, Pageable pageable);

    record ConPermiso(Expediente expediente, Permiso permiso) {}

    /** Expedientes a los que un usuario (no administrador del tenant) tiene acceso explicito. */
    @Query("""
            select new co.medtender.api.domain.ExpedienteRepository$ConPermiso(e, p.permiso)
            from Expediente e, ExpedientePermiso p
            where p.expedienteId = e.id and e.tenantId = :tenantId and p.tenantId = :tenantId
              and p.usuarioId = :usuarioId
            order by e.createdAt desc
            """)
    List<ConPermiso> visiblesPara(@Param("tenantId") UUID tenantId, @Param("usuarioId") UUID usuarioId,
                                  Pageable pageable);
}

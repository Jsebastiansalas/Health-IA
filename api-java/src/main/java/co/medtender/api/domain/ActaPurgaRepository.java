package co.medtender.api.domain;

import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ActaPurgaRepository extends JpaRepository<ActaPurga, UUID> {

    List<ActaPurga> findByDocumentoIdAndTenantIdOrderByPurgedAt(UUID documentoId, UUID tenantId);
}

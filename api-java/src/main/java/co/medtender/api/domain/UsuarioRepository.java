package co.medtender.api.domain;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UsuarioRepository extends JpaRepository<Usuario, UUID> {

    Optional<Usuario> findByEmail(String email);

    Optional<Usuario> findByIdAndTenantId(UUID id, UUID tenantId);

    List<Usuario> findByTenantIdOrderByCreatedAt(UUID tenantId, Pageable pageable);
}

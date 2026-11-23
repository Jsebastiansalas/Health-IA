package co.medtender.api.domain;

import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface VerificacionCorreoRepository extends JpaRepository<VerificacionCorreo, UUID> {

    Optional<VerificacionCorreo> findByTokenHash(String tokenHash);

    boolean existsByUsuarioIdAndUsadoAtIsNotNull(UUID usuarioId);
}

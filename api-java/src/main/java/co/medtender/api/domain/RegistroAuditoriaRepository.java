package co.medtender.api.domain;

import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface RegistroAuditoriaRepository extends JpaRepository<RegistroAuditoria, UUID> {

    @Query("""
            select a from RegistroAuditoria a
            where a.tenantId = :tenantId
              and (:accion is null or a.accion = :accion)
              and (:resultado is null or a.resultado = :resultado)
              and (:usuarioId is null or a.usuarioId = :usuarioId)
              and (:recursoId is null or a.recursoId = :recursoId)
              and a.createdAt >= :desde and a.createdAt <= :hasta
            order by a.createdAt desc
            """)
    List<RegistroAuditoria> buscar(@Param("tenantId") UUID tenantId, @Param("accion") String accion,
                                   @Param("resultado") String resultado, @Param("usuarioId") UUID usuarioId,
                                   @Param("recursoId") UUID recursoId, @Param("desde") Instant desde,
                                   @Param("hasta") Instant hasta, Pageable pageable);
}

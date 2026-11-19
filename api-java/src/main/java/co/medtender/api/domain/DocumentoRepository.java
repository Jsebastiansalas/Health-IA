package co.medtender.api.domain;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface DocumentoRepository extends JpaRepository<Documento, UUID> {

    /** Bloquea la fila para que una purga y el agente no se pisen. */
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select d from Documento d where d.id = :id")
    Optional<Documento> buscarParaActualizar(@Param("id") UUID id);

    List<Documento> findByTenantIdAndExpedienteIdOrderByUploadedAtDesc(UUID tenantId, UUID expedienteId);

    Optional<Documento> findByIdAndExpedienteIdAndTenantId(UUID id, UUID expedienteId, UUID tenantId);

    @Query("""
            select d.id from Documento d
            where d.tenantId = :tenantId and d.expedienteId = :expedienteId
              and d.sha256Original = :sha
              and d.estadoIndexacion <> co.medtender.api.domain.EstadoIndexacion.ERROR_PURGADO
            """)
    List<UUID> duplicados(@Param("tenantId") UUID tenantId, @Param("expedienteId") UUID expedienteId,
                          @Param("sha") String sha);

    /** Documentos cuyo PDF temporal podria seguir en disco (no purgados). */
    List<Documento> findByExpedienteIdAndTempFilePurgedFalse(UUID expedienteId);

    @Query(value = "select count(*) > 0 from reindexaciones where expediente_id = :id and estado in ('PENDIENTE','EN_PROCESO')",
            nativeQuery = true)
    boolean hayReindexacionActiva(@Param("id") UUID expedienteId);
}

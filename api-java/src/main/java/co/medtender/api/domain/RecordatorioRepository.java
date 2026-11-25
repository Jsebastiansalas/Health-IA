package co.medtender.api.domain;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

public interface RecordatorioRepository extends JpaRepository<Recordatorio, UUID> {

    Optional<Recordatorio> findByIdAndUsuarioId(UUID id, UUID usuarioId);

    boolean existsByUsuarioIdAndExpedienteIdAndClave(UUID usuarioId, UUID expedienteId, String clave);

    @Query("select r from Recordatorio r where r.usuarioId = :usuarioId and r.estado <> co.medtender.api.domain.Recordatorio.Estado.DESCARTADO "
            + "order by case when r.fecha is null then 1 else 0 end, r.fecha, r.createdAt")
    List<Recordatorio> vigentesDe(UUID usuarioId);

    /** Confirmados con fecha entre hoy y el límite que aún no se han avisado (para el proceso de avisos). */
    @Query("select r from Recordatorio r where r.estado = co.medtender.api.domain.Recordatorio.Estado.CONFIRMADO "
            + "and r.avisoEnviadoAt is null and r.fecha between :desde and :hasta")
    List<Recordatorio> porAvisar(LocalDate desde, LocalDate hasta);
}

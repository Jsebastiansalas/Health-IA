package co.medtender.api.privacidad;

import co.medtender.api.security.ContextoTenant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/**
 * Retencion elegida por la persona: preguntas y respuestas guardadas (incluidas explicaciones y lineas de tiempo)
 * se borran al superar el plazo. Los documentos, expedientes y recordatorios no se tocan.
 */
@Service
public class RetencionService {

    public static final List<Integer> PLAZOS = List.of(3, 6, 12, 24);

    private static final Logger log = LoggerFactory.getLogger(RetencionService.class);

    private final JdbcTemplate jdbc;

    public RetencionService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Integer meses(UUID tenantId) {
        return jdbc.queryForObject("SELECT retencion_historial_meses FROM tenants WHERE id = ?", Integer.class, tenantId);
    }

    /** Cuantas respuestas se borrarian hoy con cada plazo, para avisar antes de elegir. */
    public Map<String, Integer> seBorrarian(UUID tenantId) {
        var r = new LinkedHashMap<String, Integer>();
        for (int plazo : PLAZOS) {
            r.put(String.valueOf(plazo), jdbc.queryForObject(
                    "SELECT count(*) FROM consultas WHERE tenant_id = ? AND created_at < now() - make_interval(months => ?)",
                    Integer.class, tenantId, plazo));
        }
        return r;
    }

    /** Guarda el plazo y borra enseguida lo que ya lo supera. Devuelve cuantas se borraron. */
    public int elegir(UUID tenantId, Integer meses) {
        jdbc.update("UPDATE tenants SET retencion_historial_meses = ? WHERE id = ?", meses, tenantId);
        if (meses == null) {
            return 0;
        }
        return jdbc.update("DELETE FROM consultas WHERE tenant_id = ? AND created_at < now() - make_interval(months => ?)",
                tenantId, meses);
    }

    /** Todos los dias a las 3:15 de Colombia. Cruza tenants: corre como sistema. */
    @Scheduled(cron = "${medtender.retencion.cron:0 15 3 * * *}", zone = "America/Bogota")
    public void programado() {
        aplicar();
    }

    public int aplicar() {
        int borradas = ContextoTenant.comoSistema(() -> jdbc.update("""
                DELETE FROM consultas c USING tenants t
                WHERE c.tenant_id = t.id AND t.retencion_historial_meses IS NOT NULL
                  AND c.created_at < now() - make_interval(months => t.retencion_historial_meses)"""));
        if (borradas > 0) {
            log.info("Retención: {} respuestas guardadas borradas por superar el plazo elegido", borradas);
        }
        return borradas;
    }
}

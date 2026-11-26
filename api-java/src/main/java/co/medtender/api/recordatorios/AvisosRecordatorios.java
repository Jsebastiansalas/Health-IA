package co.medtender.api.recordatorios;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.domain.Recordatorio;
import co.medtender.api.domain.RecordatorioRepository;
import co.medtender.api.domain.UsuarioRepository;
import co.medtender.api.privacidad.CorreoEnvio;
import co.medtender.api.security.ContextoTenant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Locale;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Avisa por correo los recordatorios confirmados que llegan en los próximos días. El correo no lleva datos de
 * salud (ni el texto del documento ni el expediente): solo que hay un control en tal fecha y el enlace a la app.
 * Cada recordatorio se avisa una vez; si la persona cambia la fecha, se vuelve a poder avisar.
 */
@Component
public class AvisosRecordatorios {

    private static final Logger log = LoggerFactory.getLogger(AvisosRecordatorios.class);
    private static final ZoneId ZONA = ZoneId.of("America/Bogota");
    private static final DateTimeFormatter FECHA = DateTimeFormatter.ofPattern("EEEE d 'de' MMMM 'de' yyyy", Locale.forLanguageTag("es-CO"));

    private final RecordatorioRepository recordatorios;
    private final UsuarioRepository usuarios;
    private final CorreoEnvio correo;
    private final AuditoriaService auditoria;
    private final TransactionTemplate tx;
    private final int diasAntes;
    private final boolean activos;
    private final String baseUrl;

    private final co.medtender.api.push.PushService push;
    private final org.springframework.jdbc.core.JdbcTemplate jdbc;

    public AvisosRecordatorios(RecordatorioRepository recordatorios, UsuarioRepository usuarios, CorreoEnvio correo,
                               AuditoriaService auditoria, PlatformTransactionManager tm,
                               co.medtender.api.push.PushService push, org.springframework.jdbc.core.JdbcTemplate jdbc,
                               @Value("${medtender.recordatorios.dias-antes:3}") int diasAntes,
                               @Value("${medtender.recordatorios.avisos-activos:true}") boolean activos,
                               @Value("${medtender.correo.base-url:http://localhost:8088}") String baseUrl) {
        this.push = push;
        this.jdbc = jdbc;
        this.recordatorios = recordatorios;
        this.usuarios = usuarios;
        this.correo = correo;
        this.auditoria = auditoria;
        this.tx = new TransactionTemplate(tm);
        this.diasAntes = diasAntes;
        this.activos = activos;
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
    }

    /** Todos los días a las 8:00 de Colombia. */
    @Scheduled(cron = "${medtender.recordatorios.cron:0 0 8 * * *}", zone = "America/Bogota")
    public void programado() {
        if (activos) enviarAvisos(LocalDate.now(ZONA));
    }

    /** Envía los avisos pendientes para `hoy` y devuelve cuántos salieron. Cruza tenants: corre como sistema. */
    public int enviarAvisos(LocalDate hoy) {
        return ContextoTenant.comoSistema(() -> {
            int enviados = 0;
            for (Recordatorio r : tx.execute(s -> recordatorios.porAvisar(hoy, hoy.plusDays(diasAntes)))) {
                try {
                    if (avisar(r)) enviados++;
                } catch (RuntimeException e) {
                    log.warn("No se pudo avisar el recordatorio {}: {}", r.getId(), e.getMessage());
                }
            }
            return enviados;
        });
    }

    private boolean avisar(Recordatorio r) {
        var usuario = usuarios.findById(r.getUsuarioId()).orElse(null);
        if (usuario == null || !usuario.isActivo()) return false;
        // La notificacion va sin contenido. El correo sale si la persona lo quiere o si ningun dispositivo la recibio.
        boolean llegoAlDispositivo = push.avisar(usuario.getId());
        if (llegoAlDispositivo && !porCorreo(usuario.getId())) {
            return marcarAvisado(r, "dispositivo");
        }
        String cuerpo = "Hola.\n\n"
                + "Tienes un control médico que confirmaste para el " + FECHA.format(r.getFecha()) + ".\n\n"
                + "Puedes ver el detalle en MedTender: " + baseUrl + "/recordatorios\n\n"
                + "Por tu privacidad, este correo no incluye información de tus documentos.\n";
        try {
            correo.enviar(usuario.getEmail(), "Tienes un recordatorio en MedTender", cuerpo);
        } catch (RuntimeException e) {
            if (!llegoAlDispositivo) throw e; // se reintenta mañana
            log.warn("El aviso {} llego al dispositivo pero no por correo", r.getId());
            return marcarAvisado(r, "dispositivo");
        }
        return marcarAvisado(r, llegoAlDispositivo ? "dispositivo y correo" : "correo");
    }

    private boolean porCorreo(java.util.UUID usuarioId) {
        return jdbc.queryForObject("select recordatorios_por_correo from usuarios where id = ?", Boolean.class, usuarioId);
    }

    private boolean marcarAvisado(Recordatorio r, String por) {
        tx.executeWithoutResult(s -> recordatorios.findById(r.getId()).ifPresent(x -> {
            x.marcarAvisado();
            recordatorios.save(x);
        }));
        auditoria.auditar(Accion.AVISO_RECORDATORIO, r.getTenantId(), r.getUsuarioId(), null, "OK", "recordatorio", r.getId(),
                Map.of("por", por));
        return true;
    }
}

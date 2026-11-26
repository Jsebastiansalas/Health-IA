package co.medtender.api.push;

import co.medtender.api.security.ContextoTenant;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/** Dispositivos de cada persona y envio de avisos. Sin claves VAPID, las notificaciones quedan apagadas. */
@Service
public class PushService {

    private static final Logger log = LoggerFactory.getLogger(PushService.class);
    static final int MAXIMO_POR_PERSONA = 10;

    public record Estado(boolean disponible, String clavePublica, int dispositivos, boolean porCorreo) {}

    private final JdbcTemplate jdbc;
    private final Vapid vapid;
    private final ObjectProvider<PushEnvio> sustituto;
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10))
            .followRedirects(HttpClient.Redirect.NEVER).build(); // una redireccion saltaria la lista de destinos

    public PushService(JdbcTemplate jdbc, ObjectProvider<PushEnvio> sustituto,
                       @Value("${medtender.push.clave-publica:}") String publica,
                       @Value("${medtender.push.clave-privada:}") String privada,
                       @Value("${medtender.push.contacto:}") String contacto,
                       @Value("${medtender.correo.base-url:http://localhost:8088}") String baseUrl) {
        this.jdbc = jdbc;
        this.sustituto = sustituto;
        this.vapid = publica.isBlank() || privada.isBlank() ? null
                : new Vapid(publica.strip(), privada.strip(), contacto.isBlank() ? baseUrl : contacto.strip());
    }

    public boolean disponible() {
        return vapid != null;
    }

    public Estado estado(UsuarioActual u) {
        int dispositivos = jdbc.queryForObject("select count(*) from suscripciones_push where usuario_id = ?",
                Integer.class, u.id());
        return new Estado(disponible(), disponible() ? vapid.clavePublica() : "", dispositivos, porCorreo(u.id()));
    }

    private boolean porCorreo(UUID usuarioId) {
        return jdbc.queryForObject("select recordatorios_por_correo from usuarios where id = ?", Boolean.class, usuarioId);
    }

    public void suscribir(UsuarioActual u, String endpoint) {
        if (!disponible()) {
            throw new ApiException(HttpStatus.CONFLICT, "Las notificaciones no están activadas en este servidor");
        }
        if (!DestinoPush.permitido(endpoint)) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "Ese servicio de notificaciones no es compatible");
        }
        int otros = jdbc.queryForObject("select count(*) from suscripciones_push where usuario_id = ? and endpoint <> ?",
                Integer.class, u.id(), endpoint);
        if (otros >= MAXIMO_POR_PERSONA) {
            throw new ApiException(HttpStatus.CONFLICT, "Ya hay " + MAXIMO_POR_PERSONA + " dispositivos con avisos activados");
        }
        // Un dispositivo es de quien lo usa ahora: si antes entro otra cuenta, deja de avisarle a ella.
        ContextoTenant.comoSistema(() -> {
            jdbc.update("""
                    insert into suscripciones_push (tenant_id, usuario_id, endpoint) values (?, ?, ?)
                    on conflict (endpoint) do update set tenant_id = excluded.tenant_id, usuario_id = excluded.usuario_id,
                        created_at = now()""", u.tenantId(), u.id(), endpoint);
        });
    }

    public void darDeBaja(UsuarioActual u, String endpoint) {
        jdbc.update("delete from suscripciones_push where usuario_id = ? and endpoint = ?", u.id(), endpoint);
        asegurarAlgunAviso(u.id());
    }

    public void preferirCorreo(UsuarioActual u, boolean porCorreo) {
        if (!porCorreo && estado(u).dispositivos() == 0) {
            throw new ApiException(HttpStatus.CONFLICT, "Activa primero las notificaciones en algún dispositivo");
        }
        jdbc.update("update usuarios set recordatorios_por_correo = ? where id = ?", porCorreo, u.id());
    }

    /** Sin ningun dispositivo, el correo vuelve a estar activo: nadie se queda sin avisos sin saberlo. */
    private void asegurarAlgunAviso(UUID usuarioId) {
        jdbc.update("update usuarios set recordatorios_por_correo = true where id = ? "
                + "and not exists (select 1 from suscripciones_push where usuario_id = ?)", usuarioId, usuarioId);
    }

    /** Para el proceso de avisos (contexto de sistema). Devuelve si llego al menos a un dispositivo. */
    public boolean avisar(UUID usuarioId) {
        if (!disponible()) return false;
        List<String> destinos = jdbc.queryForList("select endpoint from suscripciones_push where usuario_id = ?",
                String.class, usuarioId);
        PushEnvio envio = sustituto.getIfAvailable(() -> this::enviarPorHttp);
        boolean llego = false;
        for (String destino : destinos) {
            switch (envio.enviar(destino)) {
                case ENVIADO -> llego = true;
                case CADUCADA -> jdbc.update("delete from suscripciones_push where endpoint = ?", destino);
                case FALLO -> { }
            }
        }
        asegurarAlgunAviso(usuarioId);
        return llego;
    }

    private PushEnvio.Resultado enviarPorHttp(String endpoint) {
        if (!DestinoPush.permitido(endpoint)) return PushEnvio.Resultado.CADUCADA;
        try {
            URI destino = URI.create(endpoint);
            var pedido = HttpRequest.newBuilder(destino).timeout(Duration.ofSeconds(15))
                    .header("Authorization", vapid.autorizacion(destino, Instant.now()))
                    .header("TTL", "86400").header("Urgency", "normal")
                    .POST(HttpRequest.BodyPublishers.noBody()).build();
            int estado = http.send(pedido, HttpResponse.BodyHandlers.discarding()).statusCode();
            if (estado >= 200 && estado < 300) return PushEnvio.Resultado.ENVIADO;
            if (estado == 404 || estado == 410) return PushEnvio.Resultado.CADUCADA;
            log.warn("El servicio de push {} respondio {}", destino.getHost(), estado);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } catch (Exception e) {
            // Sin la direccion: identifica al dispositivo de la persona.
            log.warn("No se pudo enviar una notificacion: {}", e.getClass().getSimpleName());
        }
        return PushEnvio.Resultado.FALLO;
    }
}

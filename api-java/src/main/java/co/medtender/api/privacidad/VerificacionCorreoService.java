package co.medtender.api.privacidad;

import co.medtender.api.domain.TenantRepository;
import co.medtender.api.domain.TipoTenant;
import co.medtender.api.domain.VerificacionCorreo;
import co.medtender.api.domain.VerificacionCorreoRepository;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Verificacion de correo de las cuentas personales. El enlace de un solo uso vence a las 24 horas; en la base
 * solo queda su hash. Si {@code medtender.correo.verificacion-obligatoria} es true, una cuenta personal sin
 * verificar no puede subir documentos ni consultar (403 con codigo {@code correo_no_verificado}).
 */
@Service
public class VerificacionCorreoService {

    private static final Logger log = LoggerFactory.getLogger(VerificacionCorreoService.class);
    private static final Duration VIGENCIA = Duration.ofHours(24);
    private static final SecureRandom ALEATORIO = new SecureRandom();

    private final VerificacionCorreoRepository verificaciones;
    private final TenantRepository tenants;
    private final CorreoEnvio correo;
    private final boolean obligatoria;
    private final String baseUrl;

    public VerificacionCorreoService(VerificacionCorreoRepository verificaciones, TenantRepository tenants,
                                     CorreoEnvio correo,
                                     @Value("${medtender.correo.verificacion-obligatoria:false}") boolean obligatoria,
                                     @Value("${medtender.correo.base-url:http://localhost:8088}") String baseUrl) {
        this.verificaciones = verificaciones;
        this.tenants = tenants;
        this.correo = correo;
        this.obligatoria = obligatoria;
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
    }

    public record Estado(boolean requerido, boolean verificado) {}

    private static String hash(String token) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    @Transactional(readOnly = true)
    public Estado estado(UsuarioActual u) {
        boolean personal = tenants.findById(u.tenantId()).map(t -> t.getTipo() == TipoTenant.PERSONAL).orElse(false);
        return new Estado(obligatoria && personal, verificado(u.id()));
    }

    private boolean verificado(UUID usuarioId) {
        return verificaciones.existsByUsuarioIdAndUsadoAtIsNotNull(usuarioId);
    }

    /** 403 con codigo estable para que la interfaz pida confirmar el correo. */
    public void exigir(UsuarioActual u) {
        Estado e = estado(u);
        if (e.requerido() && !e.verificado()) {
            throw new ApiException(HttpStatus.FORBIDDEN,
                    "Confirma tu correo para usar el asistente: te enviamos un enlace al registrarte",
                    Map.of("codigo", "correo_no_verificado"));
        }
    }

    /** Emite un enlace nuevo y lo envia. Un fallo de correo no debe impedir el registro: se registra y se sigue. */
    @Transactional
    public void enviar(UUID tenantId, UUID usuarioId, String email) {
        byte[] bytes = new byte[32];
        ALEATORIO.nextBytes(bytes);
        String token = HexFormat.of().formatHex(bytes);
        verificaciones.save(new VerificacionCorreo(tenantId, usuarioId, hash(token), Instant.now().plus(VIGENCIA)));
        try {
            correo.enviar(email, "Confirma tu correo en MedTender",
                    "Para activar tu cuenta abre este enlace (vale 24 horas y solo funciona una vez):\n\n"
                            + baseUrl + "/verificar-correo?token=" + token
                            + "\n\nSi no creaste una cuenta en MedTender, ignora este mensaje.");
        } catch (RuntimeException e) {
            log.error("No se pudo enviar el correo de verificacion al usuario {}: {}", usuarioId, e.toString());
        }
    }

    /** Usa el enlace: idempotente para quien ya lo uso, error claro si vencio o no existe. */
    @Transactional
    public UUID verificar(String token) {
        var v = verificaciones.findByTokenHash(hash(token == null ? "" : token.trim()))
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "El enlace no es válido"));
        if (v.getUsadoAt() != null) {
            return v.getUsuarioId();
        }
        if (v.getExpiraAt().isBefore(Instant.now())) {
            throw new ApiException(HttpStatus.GONE, "El enlace venció: pide uno nuevo desde la aplicación");
        }
        v.marcarUsado();
        return v.getUsuarioId();
    }
}

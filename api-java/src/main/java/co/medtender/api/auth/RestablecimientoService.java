package co.medtender.api.auth;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.domain.Usuario;
import co.medtender.api.domain.UsuarioRepository;
import co.medtender.api.privacidad.CorreoEnvio;
import co.medtender.api.security.PasswordService;
import co.medtender.api.web.ApiException;
import java.security.SecureRandom;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * «Olvidé mi contraseña»: enlace de un solo uso por correo que vence a los 30 minutos (en la base solo queda su
 * hash). Restablecerla invalida los demás enlaces y cierra todas las sesiones. No reemplaza la verificación en dos
 * pasos: quien la tenga activa la seguirá necesitando al ingresar.
 */
@Service
public class RestablecimientoService {

    private static final Duration VIGENCIA = Duration.ofMinutes(30);
    private static final SecureRandom ALEATORIO = new SecureRandom();

    private final UsuarioRepository usuarios;
    private final JdbcTemplate db;
    private final CorreoEnvio correo;
    private final PasswordService passwords;
    private final PoliticaContrasena politica;
    private final SesionService sesiones;
    private final AuditoriaService auditoria;
    private final String baseUrl;

    public RestablecimientoService(UsuarioRepository usuarios, JdbcTemplate db, CorreoEnvio correo, PasswordService passwords,
                                   PoliticaContrasena politica, SesionService sesiones, AuditoriaService auditoria,
                                   @Value("${medtender.correo.base-url:http://localhost:8088}") String baseUrl) {
        this.usuarios = usuarios;
        this.db = db;
        this.correo = correo;
        this.passwords = passwords;
        this.politica = politica;
        this.sesiones = sesiones;
        this.auditoria = auditoria;
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
    }

    /** Envía el enlace si la cuenta existe y está activa. La respuesta al cliente es siempre la misma. */
    @Transactional
    public void solicitar(String email) {
        Usuario u = usuarios.findByEmail(email).filter(Usuario::isActivo).orElse(null);
        if (u == null) return;
        byte[] b = new byte[32];
        ALEATORIO.nextBytes(b);
        String token = HexFormat.of().formatHex(b);
        db.update("INSERT INTO restablecimientos_clave (tenant_id, usuario_id, token_hash, expira_at) VALUES (?, ?, ?, ?)",
                u.getTenantId(), u.getId(), SesionService.hash(token), Timestamp.from(Instant.now().plus(VIGENCIA)));
        correo.enviar(u.getEmail(), "Restablece tu contraseña de MedTender",
                "Hola.\n\nPediste restablecer tu contraseña de MedTender. Abre este enlace en los próximos 30 minutos:\n\n"
                        + baseUrl + "/restablecer?token=" + token + "\n\n"
                        + "Si no fuiste tú, ignora este correo: tu contraseña sigue igual.\n");
        auditoria.auditar(Accion.RESTABLECER_SOLICITADO, u.getTenantId(), u.getId(), u.getEmail(), "OK", "usuario", u.getId(), Map.of());
    }

    private record Pendiente(UUID id, UUID usuarioId, Timestamp expira, Timestamp usado) {}

    /** Cambia la contraseña con un enlace válido. 400 con código estable si el enlace no sirve. */
    @Transactional
    public void restablecer(String token, String nueva) {
        List<Pendiente> filas = db.query(
                "SELECT id, usuario_id, expira_at, usado_at FROM restablecimientos_clave WHERE token_hash = ? FOR UPDATE",
                (rs, i) -> new Pendiente(rs.getObject(1, UUID.class), rs.getObject(2, UUID.class), rs.getTimestamp(3), rs.getTimestamp(4)),
                SesionService.hash(token == null ? "" : token));
        if (filas.isEmpty() || filas.get(0).usado() != null || filas.get(0).expira().toInstant().isBefore(Instant.now())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "El enlace no es válido o ya venció; pide uno nuevo",
                    Map.of("codigo", "enlace_invalido"));
        }
        Pendiente p = filas.get(0);
        Usuario u = usuarios.findById(p.usuarioId()).filter(Usuario::isActivo)
                .orElseThrow(() -> new ApiException(HttpStatus.BAD_REQUEST, "El enlace no es válido o ya venció; pide uno nuevo",
                        Map.of("codigo", "enlace_invalido")));
        politica.exigir(nueva, u.getEmail(), u.getNombreCompleto());
        u.setPasswordHash(passwords.hash(nueva));
        // El enlace usado y cualquier otro pendiente dejan de servir.
        db.update("UPDATE restablecimientos_clave SET usado_at = now() WHERE usuario_id = ? AND usado_at IS NULL", u.getId());
        sesiones.cerrarTodas(u);
        correo.enviar(u.getEmail(), "Tu contraseña de MedTender cambió",
                "Hola.\n\nTu contraseña de MedTender se acaba de restablecer y cerramos tus sesiones abiertas.\n\n"
                        + "Si no fuiste tú, pide un enlace nuevo en " + baseUrl + "/olvide-contrasena y escríbenos.\n");
        auditoria.auditar(Accion.CONTRASENA_RESTABLECIDA, u.getTenantId(), u.getId(), u.getEmail(), "OK", "usuario", u.getId(), Map.of());
    }
}

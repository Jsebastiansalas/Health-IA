package co.medtender.api.auth;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.domain.Usuario;
import co.medtender.api.domain.UsuarioRepository;
import co.medtender.api.privacidad.CorreoEnvio;
import co.medtender.api.security.Cifrador;
import co.medtender.api.web.ApiException;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Verificación en dos pasos con una app de autenticación (TOTP). Activarla tiene dos tiempos: se genera un secreto
 * pendiente y solo se activa cuando la persona escribe un código válido. Al activarla recibe 10 códigos de
 * respaldo de un solo uso (en la base, solo su hash) por si pierde el teléfono.
 */
@Service
public class DosPasosService {

    private static final SecureRandom ALEATORIO = new SecureRandom();
    private static final String ALFABETO = "abcdefghjkmnpqrstuvwxyz23456789"; // sin 0/o, 1/l/i

    private final UsuarioRepository usuarios;
    private final Cifrador cifrador;
    private final JdbcTemplate db;
    private final CorreoEnvio correo;
    private final AuditoriaService auditoria;

    public DosPasosService(UsuarioRepository usuarios, Cifrador cifrador, JdbcTemplate db, CorreoEnvio correo, AuditoriaService auditoria) {
        this.usuarios = usuarios;
        this.cifrador = cifrador;
        this.db = db;
        this.correo = correo;
        this.auditoria = auditoria;
    }

    public record Inicio(String secreto, String uri) {}

    @Transactional
    public Inicio iniciar(Usuario u) {
        if (u.isTotpActivo()) throw new ApiException(HttpStatus.CONFLICT, "La verificación en dos pasos ya está activa");
        String secreto = Totp.nuevoSecreto();
        u.setTotpPendiente(cifrador.cifrar(secreto));
        usuarios.save(u);
        return new Inicio(secreto, Totp.uri(secreto, u.getEmail()));
    }

    /** Activa con un código de la app y devuelve los códigos de respaldo (se muestran una sola vez). */
    @Transactional
    public List<String> activar(Usuario u, String codigo) {
        if (u.getTotpPendiente() == null) {
            throw new ApiException(HttpStatus.CONFLICT, "Primero inicia la activación para escanear el código QR");
        }
        if (!Totp.valido(cifrador.descifrar(u.getTotpPendiente()), codigo, Instant.now())) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "El código no coincide; revisa la hora del teléfono e intenta de nuevo",
                    Map.of("codigo", "codigo_invalido"));
        }
        u.activarTotp();
        usuarios.save(u);
        db.update("DELETE FROM codigos_respaldo WHERE usuario_id = ?", u.getId());
        List<String> codigos = new ArrayList<>();
        for (int i = 0; i < 10; i++) {
            String c = aleatorio(4) + "-" + aleatorio(4);
            codigos.add(c);
            db.update("INSERT INTO codigos_respaldo (tenant_id, usuario_id, codigo_hash) VALUES (?, ?, ?)",
                    u.getTenantId(), u.getId(), SesionService.hash(c));
        }
        correo.enviar(u.getEmail(), "Activaste la verificación en dos pasos en MedTender",
                "Hola.\n\nDesde ahora, al ingresar a MedTender te pediremos un código de tu app de autenticación.\n\n"
                        + "Si no fuiste tú, cambia tu contraseña de inmediato.\n");
        auditoria.auditar(Accion.DOS_PASOS_ACTIVADO, u.getTenantId(), u.getId(), u.getEmail(), "OK", "usuario", u.getId(), Map.of());
        return codigos;
    }

    @Transactional
    public void desactivar(Usuario u, String codigo) {
        if (!u.isTotpActivo()) return;
        if (!verificar(u, codigo)) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "El código no coincide", Map.of("codigo", "codigo_invalido"));
        }
        u.desactivarTotp();
        usuarios.save(u);
        db.update("DELETE FROM codigos_respaldo WHERE usuario_id = ?", u.getId());
        correo.enviar(u.getEmail(), "Desactivaste la verificación en dos pasos en MedTender",
                "Hola.\n\nLa verificación en dos pasos de tu cuenta de MedTender quedó desactivada.\n\n"
                        + "Si no fuiste tú, cambia tu contraseña y vuelve a activarla.\n");
        auditoria.auditar(Accion.DOS_PASOS_DESACTIVADO, u.getTenantId(), u.getId(), u.getEmail(), "OK", "usuario", u.getId(), Map.of());
    }

    /** Código de la app o, si no, un código de respaldo sin usar (que queda gastado). */
    @Transactional
    public boolean verificar(Usuario u, String codigo) {
        if (!u.isTotpActivo() || codigo == null) return false;
        if (Totp.valido(cifrador.descifrar(u.getTotpSecreto()), codigo, Instant.now())) return true;
        String normalizado = codigo.strip().toLowerCase().replace(" ", "");
        if (normalizado.length() == 8 && !normalizado.contains("-")) {
            normalizado = normalizado.substring(0, 4) + "-" + normalizado.substring(4);
        }
        List<UUID> ids = db.queryForList(
                "SELECT id FROM codigos_respaldo WHERE usuario_id = ? AND codigo_hash = ? AND usado_at IS NULL FOR UPDATE",
                UUID.class, u.getId(), SesionService.hash(normalizado));
        if (ids.isEmpty()) return false;
        db.update("UPDATE codigos_respaldo SET usado_at = now() WHERE id = ?", ids.get(0));
        return true;
    }

    public int respaldosDisponibles(Usuario u) {
        Integer n = db.queryForObject("SELECT count(*) FROM codigos_respaldo WHERE usuario_id = ? AND usado_at IS NULL",
                Integer.class, u.getId());
        return n == null ? 0 : n;
    }

    private static String aleatorio(int n) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < n; i++) sb.append(ALFABETO.charAt(ALEATORIO.nextInt(ALFABETO.length())));
        return sb.toString();
    }
}

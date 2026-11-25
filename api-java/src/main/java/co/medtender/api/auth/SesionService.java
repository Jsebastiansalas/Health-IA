package co.medtender.api.auth;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.auth.Dtos.TokensOut;
import co.medtender.api.domain.Usuario;
import co.medtender.api.domain.UsuarioRepository;
import co.medtender.api.security.ContextoTenant;
import co.medtender.api.security.JwtService;
import co.medtender.api.web.ApiException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Sesiones revocables. Cada inicio de sesión abre una «familia»; cada renovación ROTA el token de renovación
 * (el anterior queda usado). Presentar uno ya usado significa que alguien lo copió: se revoca toda la familia.
 * En la base solo queda el hash del identificador de cada token.
 */
@Service
public class SesionService {

    public static final String SESION_NO_VALIDA = "Tu sesión ya no es válida; vuelve a ingresar";

    private final JwtService jwt;
    private final JdbcTemplate db;
    private final UsuarioRepository usuarios;
    private final AuditoriaService auditoria;

    public SesionService(JwtService jwt, JdbcTemplate db, UsuarioRepository usuarios, AuditoriaService auditoria) {
        this.jwt = jwt;
        this.db = db;
        this.usuarios = usuarios;
        this.auditoria = auditoria;
    }

    static String hash(String jti) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(jti.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    /** Abre una sesión nueva (inicio de sesión, registro). */
    @Transactional
    public TokensOut abrir(Usuario u) {
        return emitir(u, UUID.randomUUID());
    }

    private TokensOut emitir(Usuario u, UUID familia) {
        String access = jwt.crear(u.getId(), u.getTenantId(), u.getRolGlobal(), JwtService.Tipo.ACCESS);
        var refresh = jwt.emitir(u.getId(), u.getTenantId(), u.getRolGlobal(), JwtService.Tipo.REFRESH, familia);
        db.update("INSERT INTO sesiones (tenant_id, usuario_id, familia, jti_hash, expira_at) VALUES (?, ?, ?, ?, ?)",
                u.getTenantId(), u.getId(), familia, hash(refresh.jti()), Timestamp.from(refresh.expira()));
        return TokensOut.de(access, refresh.token());
    }

    private record Fila(UUID familia, UUID usuarioId, Timestamp usadoAt, Timestamp revocadaAt) {}

    /**
     * Renueva con un refresh ya validado (firma y vencimiento). Rota el token; si estaba usado, revoca la familia.
     * Corre como sistema: aún no hay tenant en el contexto.
     */
    @Transactional(noRollbackFor = ApiException.class)
    public TokensOut renovar(Jwt refresh) {
        List<Fila> filas = db.query(
                "SELECT familia, usuario_id, usado_at, revocada_at FROM sesiones WHERE jti_hash = ? FOR UPDATE",
                (rs, i) -> new Fila(rs.getObject(1, UUID.class), rs.getObject(2, UUID.class), rs.getTimestamp(3), rs.getTimestamp(4)),
                hash(refresh.getId()));
        if (filas.isEmpty() || filas.get(0).revocadaAt() != null) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, SESION_NO_VALIDA);
        }
        Fila f = filas.get(0);
        Usuario u = usuarios.findById(f.usuarioId()).filter(Usuario::isActivo)
                .orElseThrow(() -> new ApiException(HttpStatus.UNAUTHORIZED, SESION_NO_VALIDA));
        if (f.usadoAt() != null) {
            revocarFamilia(f.familia());
            auditoria.auditar(Accion.SESION_REUTILIZADA, u.getTenantId(), u.getId(), u.getEmail(), "DENEGADO", "usuario", u.getId(),
                    Map.of("motivo", "refresh_reutilizado"));
            throw new ApiException(HttpStatus.UNAUTHORIZED, "Por seguridad cerramos esta sesión; vuelve a ingresar",
                    Map.of("codigo", "sesion_reutilizada"));
        }
        Instant emitido = JwtService.emitido(refresh);
        if (emitido == null || emitido.isBefore(u.getSesionesValidasDesde())) {
            revocarFamilia(f.familia());
            throw new ApiException(HttpStatus.UNAUTHORIZED, SESION_NO_VALIDA);
        }
        db.update("UPDATE sesiones SET usado_at = now() WHERE jti_hash = ?", hash(refresh.getId()));
        return emitir(u, f.familia());
    }

    /** Cierra la sesión a la que pertenece este refresh (todas sus renovaciones). */
    @Transactional
    public UUID cerrar(Jwt refresh) {
        Object fam = refresh.getClaims().get("fam");
        if (fam == null) return null;
        UUID familia = UUID.fromString(fam.toString());
        revocarFamilia(familia);
        return familia;
    }

    private void revocarFamilia(UUID familia) {
        db.update("UPDATE sesiones SET revocada_at = now() WHERE familia = ? AND revocada_at IS NULL", familia);
    }

    /**
     * Cierra todas las sesiones de la persona: revoca sus refresh y mueve `sesiones_validas_desde`, así hasta los
     * access tokens vigentes dejan de servir en la siguiente petición.
     */
    @Transactional
    public void cerrarTodas(Usuario u) {
        db.update("UPDATE sesiones SET revocada_at = now() WHERE usuario_id = ? AND revocada_at IS NULL", u.getId());
        u.invalidarSesiones();
        usuarios.save(u);
    }

    /** Igual que {@link #cerrarTodas} pero deja abierta una sesión nueva para quien hizo el cambio. */
    @Transactional
    public TokensOut cerrarTodasYAbrir(Usuario u) {
        cerrarTodas(u);
        return abrir(u);
    }

    /** Limpieza diaria: los registros de sesiones vencidas hace más de un día ya no sirven para nada. */
    @Scheduled(cron = "${medtender.sesiones.limpieza-cron:0 30 3 * * *}", zone = "America/Bogota")
    public void limpiar() {
        ContextoTenant.comoSistema(() -> db.update("DELETE FROM sesiones WHERE expira_at < now() - interval '1 day'"));
    }
}

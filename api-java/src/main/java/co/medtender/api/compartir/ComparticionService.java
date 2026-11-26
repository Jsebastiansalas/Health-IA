package co.medtender.api.compartir;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.domain.Permiso;
import co.medtender.api.domain.TenantRepository;
import co.medtender.api.domain.TipoTenant;
import co.medtender.api.privacidad.CorreoEnvio;
import co.medtender.api.security.ContextoTenant;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Compartir un expediente personal con un cuidador. Los correos no dicen nada de salud: ni el nombre del
 * expediente ni su contenido.
 */
@Service
public class ComparticionService {

    private static final Logger log = LoggerFactory.getLogger(ComparticionService.class);
    private static final Duration VIGENCIA = Duration.ofDays(7);
    static final int MAXIMO_POR_EXPEDIENTE = 5;
    private static final SecureRandom ALEATORIO = new SecureRandom();

    public record Comparticion(UUID id, String correo, Permiso permiso, String estado, Instant creadaAt,
                               Instant aceptadaAt, Instant expiraAt, Instant ultimoAcceso) {}

    public record Acceso(UUID tenantId, Permiso permiso) {}

    public record CompartidoConmigo(UUID expedienteId, String titulo, String compartidoPor, Permiso permiso,
                                    Instant desde) {}

    private final JdbcTemplate jdbc;
    private final TransactionTemplate tx;
    private final TenantRepository tenants;
    private final CorreoEnvio correo;
    private final AuditoriaService auditoria;
    private final String baseUrl;

    public ComparticionService(JdbcTemplate jdbc, PlatformTransactionManager tm, TenantRepository tenants,
                               CorreoEnvio correo, AuditoriaService auditoria,
                               @Value("${medtender.correo.base-url:http://localhost:8088}") String baseUrl) {
        this.jdbc = jdbc;
        this.tx = new TransactionTemplate(tm);
        this.tenants = tenants;
        this.correo = correo;
        this.auditoria = auditoria;
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
    }

    private static String hash(String token) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    public static String normalizarCorreo(String correo) {
        return correo == null ? "" : correo.strip().toLowerCase(Locale.ROOT);
    }

    public void exigirCuentaPersonal(UsuarioActual u) {
        boolean personal = tenants.findById(u.tenantId()).map(t -> t.getTipo() == TipoTenant.PERSONAL).orElse(false);
        if (!personal) {
            throw new ApiException(HttpStatus.FORBIDDEN, "Compartir con un cuidador es solo para cuentas personales",
                    Map.of("codigo", "solo_personas"));
        }
    }

    private String nombreDe(UUID usuarioId) {
        return ContextoTenant.comoSistema(() ->
                jdbc.queryForObject("select nombre_completo from usuarios where id = ?", String.class, usuarioId));
    }

    private String correoDe(UUID usuarioId) {
        return ContextoTenant.comoSistema(() ->
                jdbc.queryForObject("select email from usuarios where id = ?", String.class, usuarioId));
    }

    // ---------- la dueña (con su propio contexto; el expediente ya se comprobó) ----------

    /**
     * Crea (o reemplaza) la invitación y manda el enlace. El envío va en segundo plano: si falla después, la
     * dueña ve la invitación sin aceptar y puede volver a invitar, que reemplaza el enlace.
     */
    public Comparticion invitar(UsuarioActual duena, UUID expedienteId, String correoInvitado, Permiso permiso) {
        String para = normalizarCorreo(correoInvitado);
        if (para.equals(normalizarCorreo(duena.email()))) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "Ese es tu propio correo");
        }
        if (permiso != Permiso.LECTOR && permiso != Permiso.EDITOR) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "El permiso debe ser de lectura o de edición");
        }
        if (!correo.disponible()) {
            // El enlace solo llega por correo: sin servidor, "invitación enviada" sería mentira.
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE,
                    "Este servidor no tiene correo configurado, así que no puede enviar invitaciones.",
                    Map.of("codigo", "sin_correo"));
        }
        String nombre = nombreDe(duena.id());
        byte[] bytes = new byte[32];
        ALEATORIO.nextBytes(bytes);
        String token = HexFormat.of().formatHex(bytes);
        return tx.execute(s -> {
            // Bloquea el expediente para que dos invitaciones a la vez no se salten el máximo.
            jdbc.queryForList("select id from expedientes where id = ? for update", expedienteId);
            var previas = jdbc.queryForList("select estado from comparticiones where expediente_id = ? "
                    + "and correo_invitado = ? and estado <> 'REVOCADA'", String.class, expedienteId, para);
            if (previas.contains("ACEPTADA")) {
                throw new ApiException(HttpStatus.CONFLICT, "Esa persona ya tiene acceso; quítalo antes de volver a invitarla");
            }
            // Reenviar reemplaza el enlace anterior, que deja de valer.
            jdbc.update("update comparticiones set estado = 'REVOCADA', revocada_at = now() where expediente_id = ? "
                    + "and correo_invitado = ? and estado = 'PENDIENTE'", expedienteId, para);
            int vigentes = jdbc.queryForObject("select count(*) from comparticiones where expediente_id = ? and "
                    + "(estado = 'ACEPTADA' or (estado = 'PENDIENTE' and expira_at > now()))", Integer.class, expedienteId);
            if (vigentes >= MAXIMO_POR_EXPEDIENTE) {
                throw new ApiException(HttpStatus.CONFLICT,
                        "Un expediente se puede compartir con " + MAXIMO_POR_EXPEDIENTE + " personas como máximo");
            }
            Instant expira = Instant.now().plus(VIGENCIA);
            UUID id = jdbc.queryForObject("""
                    insert into comparticiones (tenant_id, expediente_id, invitado_por, correo_invitado, permiso,
                        token_hash, expira_at) values (?, ?, ?, ?, ?, ?, ?) returning id""",
                    UUID.class, duena.tenantId(), expedienteId, duena.id(), para, permiso.name(), hash(token),
                    Timestamp.from(expira));
            try {
                correo.enviar(para, "Te invitaron a cuidar un expediente en MedTender",
                        nombre + " quiere compartir contigo un expediente en MedTender.\n\n"
                                + "Para aceptar, ingresa o crea tu cuenta con este mismo correo y abre el enlace "
                                + "(vale 7 días y solo funciona una vez):\n\n" + baseUrl + "/invitacion?token=" + token
                                + "\n\nSi no esperabas esta invitación, ignora este mensaje.\n"
                                + "Por privacidad, este correo no incluye información de salud.\n");
            } catch (RuntimeException e) {
                log.error("No se pudo enviar la invitación {}: {}", id, e.getClass().getSimpleName());
                throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE,
                        "No pudimos enviar el correo de invitación. Intenta de nuevo en un momento.");
            }
            return new Comparticion(id, para, permiso, "PENDIENTE", Instant.now(), null, expira, null);
        });
    }

    /** Las vigentes de un expediente, con la última vez que cada cuidador entró (según la auditoría). */
    public List<Comparticion> listar(UsuarioActual duena, UUID expedienteId) {
        return jdbc.query("""
                select c.id, c.correo_invitado, c.permiso, c.estado, c.created_at, c.aceptada_at, c.expira_at,
                       c.ultimo_acceso_at
                  from comparticiones c
                 where c.tenant_id = ? and c.expediente_id = ?
                   and (c.estado = 'ACEPTADA' or (c.estado = 'PENDIENTE' and c.expira_at > now()))
                 order by c.created_at""",
                (rs, n) -> new Comparticion(rs.getObject("id", UUID.class), rs.getString("correo_invitado"),
                        Permiso.valueOf(rs.getString("permiso")), rs.getString("estado"), instante(rs.getTimestamp("created_at")),
                        instante(rs.getTimestamp("aceptada_at")), instante(rs.getTimestamp("expira_at")),
                        instante(rs.getTimestamp("ultimo_acceso_at"))),
                duena.tenantId(), expedienteId);
    }

    private static Instant instante(Timestamp t) {
        return t == null ? null : t.toInstant();
    }

    public void revocar(UsuarioActual duena, UUID expedienteId, UUID comparticionId) {
        var filas = jdbc.queryForList("select invitado_usuario_id from comparticiones where id = ? and tenant_id = ? "
                + "and expediente_id = ? and estado <> 'REVOCADA'", comparticionId, duena.tenantId(), expedienteId);
        if (filas.isEmpty()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "Esa invitación ya no existe");
        }
        jdbc.update("update comparticiones set estado = 'REVOCADA', revocada_at = now() where id = ? and tenant_id = ?",
                comparticionId, duena.tenantId());
        UUID invitado = (UUID) filas.get(0).get("invitado_usuario_id");
        if (invitado != null) {
            borrarRecordatorios(invitado, expedienteId);
        }
        auditoria.auditar(Accion.COMPARTICION_REVOCADA, duena, "expediente", expedienteId,
                Map.of("comparticion", comparticionId.toString()));
    }

    /** Un recordatorio guarda una cita del documento: sin acceso al expediente, no puede conservarse. */
    private void borrarRecordatorios(UUID usuarioId, UUID expedienteId) {
        ContextoTenant.comoSistema(() -> {
            jdbc.update("delete from recordatorios where usuario_id = ? and expediente_id = ?", usuarioId, expedienteId);
        });
    }

    // ---------- el cuidador ----------

    /** Acepta con el enlace. Solo la cuenta del correo invitado; cualquier otra cosa responde lo mismo. */
    public CompartidoConmigo aceptar(UsuarioActual cuidador, String token) {
        exigirCuentaPersonal(cuidador);
        String huella = hash(token == null ? "" : token.strip());
        String miCorreo = normalizarCorreo(cuidador.email());
        record Pendiente(UUID id, UUID tenantId, UUID expedienteId, UUID duenaId) {}
        Pendiente p = ContextoTenant.comoSistema(() -> tx.execute(s -> {
            var filas = jdbc.query("""
                    select id, tenant_id, expediente_id, invitado_por from comparticiones
                     where token_hash = ? and estado = 'PENDIENTE' and expira_at > now() and correo_invitado = ?
                     for update""",
                    (rs, n) -> new Pendiente(rs.getObject("id", UUID.class), rs.getObject("tenant_id", UUID.class),
                            rs.getObject("expediente_id", UUID.class), rs.getObject("invitado_por", UUID.class)),
                    huella, miCorreo);
            if (filas.isEmpty()) {
                throw new ApiException(HttpStatus.NOT_FOUND,
                        "El enlace no es válido para esta cuenta o ya venció. Pide una invitación nueva a tu mismo correo.");
            }
            jdbc.update("update comparticiones set estado = 'ACEPTADA', aceptada_at = now(), invitado_usuario_id = ?, "
                    + "invitado_tenant_id = ? where id = ?", cuidador.id(), cuidador.tenantId(), filas.get(0).id());
            return filas.get(0);
        }));
        anotarEnLaDeLaDuena(Accion.COMPARTICION_ACEPTADA, p.tenantId(), cuidador, p.expedienteId(),
                Map.of("comparticion", p.id().toString()));
        avisar(p.duenaId(), "Aceptaron tu invitación en MedTender",
                nombreDe(cuidador.id()) + " aceptó tu invitación y ya puede ver el expediente que compartiste.\n\n"
                        + "Puedes quitar ese acceso cuando quieras desde el expediente: " + baseUrl + "/\n");
        return compartidosConmigo(cuidador).stream().filter(c -> c.expedienteId().equals(p.expedienteId())).findFirst()
                .orElseThrow();
    }

    public List<CompartidoConmigo> compartidosConmigo(UsuarioActual cuidador) {
        return ContextoTenant.comoSistema(() -> jdbc.query("""
                select c.expediente_id, e.titulo, u.nombre_completo, c.permiso, c.aceptada_at
                  from comparticiones c
                  join expedientes e on e.id = c.expediente_id
                  join usuarios u on u.id = c.invitado_por and u.activo
                 where c.invitado_usuario_id = ? and c.estado = 'ACEPTADA'
                 order by c.aceptada_at""",
                (rs, n) -> new CompartidoConmigo(rs.getObject("expediente_id", UUID.class), rs.getString("titulo"),
                        rs.getString("nombre_completo"), Permiso.valueOf(rs.getString("permiso")),
                        instante(rs.getTimestamp("aceptada_at"))),
                cuidador.id()));
    }

    /** Se consulta con el contexto del propio cuidador: la base solo le deja leer las suyas. */
    public Optional<Acceso> accesoVigente(UsuarioActual cuidador, UUID expedienteId) {
        return jdbc.query("select tenant_id, permiso from comparticiones where expediente_id = ? "
                        + "and invitado_usuario_id = ? and invitado_tenant_id = ? and estado = 'ACEPTADA'",
                (rs, n) -> new Acceso(rs.getObject("tenant_id", UUID.class), Permiso.valueOf(rs.getString("permiso"))),
                expedienteId, cuidador.id(), cuidador.tenantId()).stream().findFirst();
    }

    /**
     * Anota que el cuidador entró: la dueña ve cuándo fue la última vez y queda en su auditoría. Como mucho una
     * vez cada diez minutos, para que abrir varias pestañas no llene el registro. Antes de entrar como invitado.
     */
    public void registrarEntrada(UsuarioActual cuidador, UUID tenantDeLaDuena, UUID expedienteId) {
        int anotadas = ContextoTenant.comoSistema(() -> jdbc.update(
                "update comparticiones set ultimo_acceso_at = now() where expediente_id = ? and invitado_usuario_id = ? "
                        + "and estado = 'ACEPTADA' and (ultimo_acceso_at is null "
                        + "or ultimo_acceso_at < now() - interval '10 minutes')",
                expedienteId, cuidador.id()));
        if (anotadas == 1) {
            anotarEnLaDeLaDuena(Accion.ACCESO_COMPARTIDO, tenantDeLaDuena, cuidador, expedienteId, Map.of());
        }
    }

    public String quienComparte(UsuarioActual cuidador, UUID expedienteId) {
        return compartidosConmigo(cuidador).stream().filter(c -> c.expedienteId().equals(expedienteId))
                .map(CompartidoConmigo::compartidoPor).findFirst().orElse(null);
    }

    public void salir(UsuarioActual cuidador, UUID expedienteId) {
        record Mia(UUID id, UUID tenantId, UUID duenaId) {}
        Mia mia = ContextoTenant.comoSistema(() -> jdbc.query(
                "select id, tenant_id, invitado_por from comparticiones where expediente_id = ? and invitado_usuario_id = ? "
                        + "and estado = 'ACEPTADA'",
                (rs, n) -> new Mia(rs.getObject("id", UUID.class), rs.getObject("tenant_id", UUID.class),
                        rs.getObject("invitado_por", UUID.class)),
                expedienteId, cuidador.id()).stream().findFirst().orElse(null));
        if (mia == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "No tienes ese expediente compartido");
        }
        ContextoTenant.comoSistema(() -> {
            jdbc.update("update comparticiones set estado = 'REVOCADA', revocada_at = now() where id = ?", mia.id());
        });
        borrarRecordatorios(cuidador.id(), expedienteId);
        anotarEnLaDeLaDuena(Accion.COMPARTICION_REVOCADA, mia.tenantId(), cuidador, expedienteId,
                Map.of("comparticion", mia.id().toString(), "por", "invitado"));
        avisar(mia.duenaId(), "Dejaron un expediente que compartiste en MedTender",
                nombreDe(cuidador.id()) + " dejó de tener acceso a un expediente que habías compartido.\n");
    }

    /** El evento va al registro de la dueña, a nombre del cuidador. */
    private void anotarEnLaDeLaDuena(Accion accion, UUID tenantDeLaDuena, UsuarioActual cuidador, UUID expedienteId,
                                     Map<String, Object> detalle) {
        auditoria.auditar(accion, tenantDeLaDuena, cuidador.id(), cuidador.email(), "OK", "expediente", expedienteId,
                detalle);
    }

    /** Un aviso que no sale no deshace lo hecho. */
    private void avisar(UUID usuarioId, String asunto, String cuerpo) {
        try {
            correo.enviar(correoDe(usuarioId), asunto,
                    "Hola.\n\n" + cuerpo + "\nPor privacidad, este correo no incluye información de salud.\n");
        } catch (RuntimeException e) {
            log.error("No se pudo avisar al usuario {}: {}", usuarioId, e.getClass().getSimpleName());
        }
    }
}

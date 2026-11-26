package co.medtender.api.auth;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.auth.Dtos.LoginIn;
import co.medtender.api.auth.Dtos.RefreshIn;
import co.medtender.api.auth.Dtos.RegistroPersonalIn;
import co.medtender.api.auth.Dtos.RegistroTenantIn;
import co.medtender.api.auth.Dtos.TokensOut;
import co.medtender.api.auth.Dtos.UsuarioOut;
import co.medtender.api.config.MedtenderProperties;
import co.medtender.api.domain.Usuario;
import co.medtender.api.domain.UsuarioRepository;
import co.medtender.api.limites.Limitador;
import co.medtender.api.security.ContextoTenant;
import co.medtender.api.security.JwtService;
import co.medtender.api.security.PasswordService;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import jakarta.validation.Valid;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import org.slf4j.MDC;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private final UsuarioRepository usuarios;
    private final IdentidadService identidad;
    private final PasswordService passwords;
    private final JwtService jwt;
    private final Limitador limitador;
    private final AuditoriaService auditoria;
    private final MedtenderProperties props;
    private final co.medtender.api.privacidad.VerificacionCorreoService verificacionCorreo;
    private final SesionService sesiones;
    private final PoliticaContrasena politica;
    @org.springframework.beans.factory.annotation.Value("${medtender.registro-personal-abierto:true}")
    private boolean registroPersonalAbierto;

    public AuthController(UsuarioRepository usuarios, IdentidadService identidad, PasswordService passwords,
                          JwtService jwt, Limitador limitador, AuditoriaService auditoria,
                          MedtenderProperties props,
                          co.medtender.api.privacidad.VerificacionCorreoService verificacionCorreo,
                          SesionService sesiones, PoliticaContrasena politica) {
        this.verificacionCorreo = verificacionCorreo;
        this.sesiones = sesiones;
        this.politica = politica;
        this.usuarios = usuarios;
        this.identidad = identidad;
        this.passwords = passwords;
        this.jwt = jwt;
        this.limitador = limitador;
        this.auditoria = auditoria;
        this.props = props;
    }

    private static String ip() {
        String ip = MDC.get("ip");
        return ip == null ? "desconocida" : ip;
    }

    private TokensOut tokens(Usuario u) {
        return sesiones.abrir(u);
    }

    /** Alta de una organizacion (hospital, aseguradora...) con su primer ADMIN_TENANT. */
    @PostMapping("/registro-tenant")
    @ResponseStatus(HttpStatus.CREATED)
    public TokensOut registrarTenant(@Valid @RequestBody RegistroTenantIn in) {
        // Aun no hay tenant ni usuario: el alta cruza tenants por naturaleza.
        return ContextoTenant.comoSistema(() -> registrarTenantInterno(in));
    }

    private TokensOut registrarTenantInterno(RegistroTenantIn in) {
        var rl = props.rateLimit();
        if (!props.allowTenantSignup()) {
            throw new ApiException(HttpStatus.FORBIDDEN, "El registro de tenants está deshabilitado");
        }
        limitador.exigir("registro", ip(), rl.registroIpHora(), 3600);
        politica.exigir(in.adminPassword(), in.adminEmail(), in.adminNombre());
        // El hash (~250 ms de CPU) se calcula antes de tocar la base de datos.
        String hash = passwords.hash(in.adminPassword());
        var r = identidad.registrarTenant(in.tenantNombre(), in.nit(), in.politicaBorrado(),
                in.adminEmail().toLowerCase(Locale.ROOT), hash, in.adminNombre());
        auditoria.auditar(Accion.REGISTRO_TENANT, r.tenant().getId(), r.admin().getId(), r.admin().getEmail(),
                "OK", "tenant", r.tenant().getId(), null);
        return tokens(r.admin());
    }

    /** Alta de una cuenta personal (paciente o familiar). Tiene su propio interruptor y su limite de tasa. */
    @PostMapping("/registro-personal")
    @ResponseStatus(HttpStatus.CREATED)
    public TokensOut registrarPersonal(@Valid @RequestBody RegistroPersonalIn in) {
        return ContextoTenant.comoSistema(() -> registrarPersonalInterno(in));
    }

    private TokensOut registrarPersonalInterno(RegistroPersonalIn in) {
        if (!registroPersonalAbierto) {
            throw new ApiException(HttpStatus.FORBIDDEN, "El registro de cuentas personales está deshabilitado");
        }
        limitador.exigir("registro", ip(), props.rateLimit().registroIpHora(), 3600);
        politica.exigir(in.password(), in.email(), in.nombre());
        String hash = passwords.hash(in.password());
        var r = identidad.registrarPersonal(in.nombre().trim(), in.email().toLowerCase(Locale.ROOT), hash);
        auditoria.auditar(Accion.REGISTRO_PERSONAL, r.tenant().getId(), r.admin().getId(), r.admin().getEmail(),
                "OK", "tenant", r.tenant().getId(), null);
        verificacionCorreo.enviar(r.tenant().getId(), r.admin().getId(), r.admin().getEmail());
        return tokens(r.admin());
    }

    @PostMapping("/login")
    public Dtos.LoginOut login(@Valid @RequestBody LoginIn in) {
        // Se busca al usuario por correo, antes de saber a que tenant pertenece.
        return ContextoTenant.comoSistema(() -> loginInterno(in));
    }

    private Dtos.LoginOut loginInterno(LoginIn in) {
        var rl = props.rateLimit();
        String ip = ip();
        String email = in.email().toLowerCase(Locale.ROOT);
        limitador.exigir("login_ip", ip, rl.loginIpMin(), 60);

        // Bloqueo por fallos del par (IP, correo): un atacante en otra IP no puede dejar fuera al
        // usuario legitimo, y quien adivina contrasenas desde una IP queda frenado.
        String par = ip + "|" + email;
        var estado = limitador.excedido("login_fallos", par, rl.loginFallosPar(), rl.loginFallosVentanaS());
        if (!estado.permitido()) {
            auditoria.auditar(Accion.LOGIN_BLOQUEADO, null, null, email, "DENEGADO", null, null, null);
            throw limitador.rechazar("login_fallos", estado.reintentarEnS());
        }

        // Sin transaccion abierta: ninguna conexion del pool queda retenida durante el hash.
        Usuario u = usuarios.findByEmail(email).orElse(null);
        boolean valido = !PasswordService.excedeLimite(in.password())
                && passwords.verificar(in.password(), u == null ? null : u.getPasswordHash());
        if (u == null || !valido || !u.isActivo()) {
            limitador.golpear("login_fallos", par, rl.loginFallosPar(), rl.loginFallosVentanaS());
            auditoria.auditar(Accion.LOGIN_FALLIDO, u == null ? null : u.getTenantId(),
                    u == null ? null : u.getId(), email, "DENEGADO", null, null,
                    Map.of("motivo", u != null && valido ? "inactivo" : "credenciales"));
            throw new ApiException(HttpStatus.UNAUTHORIZED, "Credenciales inválidas");
        }
        if (u.isTotpActivo()) {
            // Contraseña correcta, falta el segundo paso: un desafío de 5 minutos en lugar de los tokens.
            String desafio = jwt.crear(u.getId(), u.getTenantId(), u.getRolGlobal(), JwtService.Tipo.DOS_PASOS);
            return Dtos.LoginOut.dosPasos(desafio);
        }
        auditoria.auditar(Accion.LOGIN_OK, u.getTenantId(), u.getId(), email, "OK", null, null, null);
        return Dtos.LoginOut.de(tokens(u));
    }

    @PostMapping("/refresh")
    public TokensOut refresh(@Valid @RequestBody RefreshIn in) {
        return ContextoTenant.comoSistema(() -> refreshInterno(in));
    }

    private TokensOut refreshInterno(RefreshIn in) {
        limitador.exigir("refresh", ip(), props.rateLimit().refreshIpMin(), 60);
        org.springframework.security.oauth2.jwt.Jwt refresh;
        try {
            refresh = jwt.leer(in.refreshToken(), JwtService.Tipo.REFRESH);
            UUID.fromString(refresh.getSubject());
        } catch (JwtException | IllegalArgumentException e) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "Refresh token inválido");
        }
        // Rota el token y relee el usuario (un cambio de rol se refleja en el nuevo access token).
        return sesiones.renovar(refresh);
    }

    @GetMapping("/me")
    public UsuarioOut me(@AuthenticationPrincipal UsuarioActual actual) {
        return UsuarioOut.de(usuarios.findById(actual.id()).orElseThrow());
    }
}

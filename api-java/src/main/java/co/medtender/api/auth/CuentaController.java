package co.medtender.api.auth;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.auth.Dtos.TokensOut;
import co.medtender.api.domain.Usuario;
import co.medtender.api.domain.UsuarioRepository;
import co.medtender.api.limites.Limitador;
import co.medtender.api.privacidad.CorreoEnvio;
import co.medtender.api.security.ContextoTenant;
import co.medtender.api.security.JwtService;
import co.medtender.api.security.PasswordService;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/**
 * Seguridad de la cuenta: cerrar sesión, cerrar todas las sesiones, cambiar y restablecer la contraseña, y la
 * verificación en dos pasos. Cada cambio sensible avisa por correo y queda en la auditoría sin datos de salud.
 */
@RestController
@RequestMapping("/api/v1/auth")
public class CuentaController {

    private final UsuarioRepository usuarios;
    private final SesionService sesiones;
    private final RestablecimientoService restablecimiento;
    private final DosPasosService dosPasos;
    private final PoliticaContrasena politica;
    private final PasswordService passwords;
    private final JwtService jwt;
    private final Limitador limitador;
    private final AuditoriaService auditoria;
    private final CorreoEnvio correo;
    private final String baseUrl;

    public CuentaController(UsuarioRepository usuarios, SesionService sesiones, RestablecimientoService restablecimiento,
                            DosPasosService dosPasos, PoliticaContrasena politica, PasswordService passwords, JwtService jwt,
                            Limitador limitador, AuditoriaService auditoria, CorreoEnvio correo,
                            @Value("${medtender.correo.base-url:http://localhost:8088}") String baseUrl) {
        this.usuarios = usuarios;
        this.sesiones = sesiones;
        this.restablecimiento = restablecimiento;
        this.dosPasos = dosPasos;
        this.politica = politica;
        this.passwords = passwords;
        this.jwt = jwt;
        this.limitador = limitador;
        this.auditoria = auditoria;
        this.correo = correo;
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
    }

    public record LogoutIn(String refreshToken) {}
    public record CambioIn(@NotBlank String actual, @NotBlank String nueva) {}
    public record OlvideIn(@NotBlank @Email @Size(max = 150) String email) {}
    public record RestablecerIn(@NotBlank String token, @NotBlank String password) {}
    public record CodigoIn(@NotBlank String codigo) {}
    public record DesactivarIn(@NotBlank String password, @NotBlank String codigo) {}
    public record VerificarIn(@NotBlank String desafio, @NotBlank String codigo) {}
    public record EstadoDosPasos(boolean activo, int respaldosDisponibles) {}
    public record CodigosRespaldo(List<String> codigosRespaldo) {}

    private static String ip() {
        String ip = MDC.get("ip");
        return ip == null ? "desconocida" : ip;
    }

    private Usuario yo(UsuarioActual a) {
        return usuarios.findById(a.id()).orElseThrow(() -> new ApiException(HttpStatus.UNAUTHORIZED, "Usuario inexistente"));
    }

    // ---------- Sesiones ----------

    /** Cierra esta sesión (y todas sus renovaciones). Idempotente: un token vencido o ajeno no da error. */
    @PostMapping("/logout")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void logout(@RequestBody(required = false) LogoutIn in) {
        if (in == null || in.refreshToken() == null) return;
        limitador.exigir("logout", ip(), 60, 60);
        Jwt refresh;
        try {
            refresh = jwt.leer(in.refreshToken(), JwtService.Tipo.REFRESH);
        } catch (JwtException e) {
            return;
        }
        UUID usuarioId = UUID.fromString(refresh.getSubject());
        UUID tenantId = UUID.fromString(refresh.getClaimAsString("tenant_id"));
        ContextoTenant.comoSistema(() -> sesiones.cerrar(refresh));
        auditoria.auditar(Accion.LOGOUT, tenantId, usuarioId, null, "OK", "usuario", usuarioId, Map.of());
    }

    /** Cierra las sesiones de todos los dispositivos y deja abierta una nueva en este. */
    @PostMapping("/cerrar-sesiones")
    public TokensOut cerrarSesiones(@AuthenticationPrincipal UsuarioActual actual) {
        Usuario u = yo(actual);
        TokensOut t = sesiones.cerrarTodasYAbrir(u);
        auditoria.auditar(Accion.SESIONES_CERRADAS, actual, "usuario", u.getId(), Map.of());
        return t;
    }

    // ---------- Contraseña ----------

    @PostMapping("/cambiar-contrasena")
    public TokensOut cambiar(@Valid @RequestBody CambioIn in, @AuthenticationPrincipal UsuarioActual actual) {
        limitador.exigir("cambiar_contrasena", actual.id().toString(), 5, 900);
        Usuario u = yo(actual);
        if (PasswordService.excedeLimite(in.actual()) || !passwords.verificar(in.actual(), u.getPasswordHash())) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "La contraseña actual no es correcta", Map.of("codigo", "contrasena_actual"));
        }
        if (in.actual().equals(in.nueva())) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "La nueva contraseña debe ser distinta", Map.of("codigo", "contrasena_igual"));
        }
        politica.exigir(in.nueva(), u.getEmail(), u.getNombreCompleto());
        u.setPasswordHash(passwords.hash(in.nueva()));
        TokensOut t = sesiones.cerrarTodasYAbrir(u);
        correo.enviar(u.getEmail(), "Tu contraseña de MedTender cambió",
                "Hola.\n\nCambiaste la contraseña de tu cuenta de MedTender y cerramos tus otras sesiones.\n\n"
                        + "Si no fuiste tú, restablécela en " + baseUrl + "/olvide-contrasena y escríbenos.\n");
        auditoria.auditar(Accion.CONTRASENA_CAMBIADA, actual, "usuario", u.getId(), Map.of());
        return t;
    }

    /** Siempre la misma respuesta, exista o no la cuenta (no revela qué correos están registrados). */
    @PostMapping("/olvide-contrasena")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public Map<String, String> olvide(@Valid @RequestBody OlvideIn in) {
        String email = in.email().toLowerCase(Locale.ROOT);
        limitador.exigir("olvide_ip", ip(), 10, 3600);
        if (limitador.excedido("olvide_correo", email, 3, 3600).permitido()) {
            limitador.golpear("olvide_correo", email, 3, 3600);
            ContextoTenant.comoSistema(() -> restablecimiento.solicitar(email));
        }
        return Map.of("mensaje", "Si hay una cuenta con ese correo, te enviamos un enlace para restablecer la contraseña.");
    }

    @PostMapping("/restablecer-contrasena")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void restablecer(@Valid @RequestBody RestablecerIn in) {
        limitador.exigir("restablecer_ip", ip(), 20, 3600);
        ContextoTenant.comoSistema(() -> restablecimiento.restablecer(in.token(), in.password()));
    }

    // ---------- Verificación en dos pasos ----------

    @GetMapping("/2fa")
    public EstadoDosPasos estado(@AuthenticationPrincipal UsuarioActual actual) {
        Usuario u = yo(actual);
        return new EstadoDosPasos(u.isTotpActivo(), u.isTotpActivo() ? dosPasos.respaldosDisponibles(u) : 0);
    }

    @PostMapping("/2fa/iniciar")
    public DosPasosService.Inicio iniciar(@AuthenticationPrincipal UsuarioActual actual) {
        return dosPasos.iniciar(yo(actual));
    }

    @PostMapping("/2fa/activar")
    public CodigosRespaldo activar(@Valid @RequestBody CodigoIn in, @AuthenticationPrincipal UsuarioActual actual) {
        limitador.exigir("2fa_activar", actual.id().toString(), 10, 600);
        return new CodigosRespaldo(dosPasos.activar(yo(actual), in.codigo()));
    }

    @PostMapping("/2fa/desactivar")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void desactivar(@Valid @RequestBody DesactivarIn in, @AuthenticationPrincipal UsuarioActual actual) {
        limitador.exigir("2fa_desactivar", actual.id().toString(), 5, 900);
        Usuario u = yo(actual);
        if (PasswordService.excedeLimite(in.password()) || !passwords.verificar(in.password(), u.getPasswordHash())) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "La contraseña no es correcta", Map.of("codigo", "contrasena_actual"));
        }
        dosPasos.desactivar(u, in.codigo());
    }

    /** Segundo paso del ingreso: el desafío que dio /login más un código de la app o de respaldo. */
    @PostMapping("/2fa/verificar")
    public TokensOut verificar(@Valid @RequestBody VerificarIn in) {
        Jwt desafio;
        try {
            desafio = jwt.leer(in.desafio(), JwtService.Tipo.DOS_PASOS);
        } catch (JwtException e) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "El ingreso venció; vuelve a escribir tu contraseña", Map.of("codigo", "desafio_vencido"));
        }
        UUID id = UUID.fromString(desafio.getSubject());
        // Cinco intentos cada cinco minutos por cuenta: un código de 6 dígitos no se puede adivinar así.
        limitador.exigir("2fa_verificar", id.toString(), 5, 300);
        return ContextoTenant.comoSistema(() -> {
            Usuario u = usuarios.findById(id).filter(Usuario::isActivo)
                    .orElseThrow(() -> new ApiException(HttpStatus.UNAUTHORIZED, "Credenciales inválidas"));
            if (JwtService.emitido(desafio) == null || JwtService.emitido(desafio).isBefore(u.getSesionesValidasDesde())) {
                throw new ApiException(HttpStatus.UNAUTHORIZED, "El ingreso venció; vuelve a escribir tu contraseña", Map.of("codigo", "desafio_vencido"));
            }
            if (!dosPasos.verificar(u, in.codigo())) {
                auditoria.auditar(Accion.DOS_PASOS_FALLIDO, u.getTenantId(), u.getId(), u.getEmail(), "DENEGADO", "usuario", u.getId(), Map.of());
                throw new ApiException(HttpStatus.UNAUTHORIZED, "El código no coincide", Map.of("codigo", "codigo_invalido"));
            }
            auditoria.auditar(Accion.LOGIN_OK, u.getTenantId(), u.getId(), u.getEmail(), "OK", null, null, Map.of("dos_pasos", true));
            return sesiones.abrir(u);
        });
    }
}

package co.medtender.api.privacidad;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.security.ContextoTenant;
import co.medtender.api.domain.UsuarioRepository;
import co.medtender.api.limites.Limitador;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Confirmacion de correo de las cuentas personales. */
@RestController
@RequestMapping("/api/v1/auth")
public class VerificacionCorreoController {

    public record VerificarIn(@NotBlank @Size(max = 200) String token) {}

    private final VerificacionCorreoService verificacion;
    private final UsuarioRepository usuarios;
    private final Limitador limitador;
    private final AuditoriaService auditoria;

    public VerificacionCorreoController(VerificacionCorreoService verificacion, UsuarioRepository usuarios,
                                        Limitador limitador, AuditoriaService auditoria) {
        this.verificacion = verificacion;
        this.usuarios = usuarios;
        this.limitador = limitador;
        this.auditoria = auditoria;
    }

    /** Se abre desde el enlace del correo, sin sesion: el token es la credencial. Limitado por IP. */
    @PostMapping("/verificar-correo")
    public Map<String, Object> verificar(@Valid @RequestBody VerificarIn in) {
        String ip = org.slf4j.MDC.get("ip") == null ? "desconocida" : org.slf4j.MDC.get("ip");
        limitador.exigir("verificar_correo", ip, 20, 3600);
        var usuarioId = ContextoTenant.comoSistema(() -> verificacion.verificar(in.token()));
        var u = ContextoTenant.comoSistema(() -> usuarios.findById(usuarioId).orElse(null));
        if (u != null) {
            auditoria.auditar(Accion.CORREO_VERIFICADO, u.getTenantId(), u.getId(), u.getEmail(), "OK", "usuario",
                    u.getId(), null);
        }
        return Map.of("verificado", true);
    }

    /** Reenvia el enlace a la cuenta que lo pide (autenticada). Maximo 3 por hora. */
    @PostMapping("/reenviar-verificacion")
    public ResponseEntity<Void> reenviar(@AuthenticationPrincipal UsuarioActual user) {
        if (verificacion.estado(user).verificado()) {
            return ResponseEntity.noContent().build();
        }
        limitador.exigir("reenviar_verificacion", user.id().toString(), 3, 3600);
        var u = usuarios.findById(user.id()).orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "Usuario no encontrado"));
        verificacion.enviar(u.getTenantId(), u.getId(), u.getEmail());
        return ResponseEntity.noContent().build();
    }
}

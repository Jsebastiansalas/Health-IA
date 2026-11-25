package co.medtender.api.privacidad;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.domain.Permiso;
import co.medtender.api.domain.UsuarioRepository;
import co.medtender.api.expediente.AutorizacionExpediente;
import co.medtender.api.security.PasswordService;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Consentimiento informado y derecho de supresion (historial y cuenta personal). */
@RestController
@RequestMapping("/api/v1")
public class PrivacidadController {

    public record ConsentimientoOut(String version, boolean requerido, boolean aceptado, Instant aceptadoAt,
                                    String tipoCuenta, boolean correoRequerido, boolean correoVerificado,
                                    String proveedorIa, String respaldoIa) {
        static ConsentimientoOut de(ConsentimientoService.Estado e, VerificacionCorreoService.Estado c) {
            return new ConsentimientoOut(e.version(), e.requerido(), e.aceptado(), e.aceptadoAt(), e.tipoCuenta().name(),
                    c.requerido(), c.verificado(), e.proveedorIa(), e.respaldoIa());
        }
    }

    /** La version del texto que la persona tenia en pantalla al aceptar. */
    public record AceptarIn(@NotBlank @Size(max = 30) String version) {}

    public record EliminarCuentaIn(@NotBlank String password) {}

    private final ConsentimientoService consentimiento;
    private final PrivacidadService privacidad;
    private final AutorizacionExpediente autorizacion;
    private final AuditoriaService auditoria;
    private final UsuarioRepository usuarios;
    private final PasswordService passwords;
    private final VerificacionCorreoService verificacionCorreo;

    public PrivacidadController(ConsentimientoService consentimiento, PrivacidadService privacidad,
                                AutorizacionExpediente autorizacion, AuditoriaService auditoria,
                                UsuarioRepository usuarios, PasswordService passwords,
                                VerificacionCorreoService verificacionCorreo) {
        this.verificacionCorreo = verificacionCorreo;
        this.consentimiento = consentimiento;
        this.privacidad = privacidad;
        this.autorizacion = autorizacion;
        this.auditoria = auditoria;
        this.usuarios = usuarios;
        this.passwords = passwords;
    }

    @GetMapping("/consentimiento")
    public ConsentimientoOut estado(@AuthenticationPrincipal UsuarioActual user) {
        return ConsentimientoOut.de(consentimiento.estado(user), verificacionCorreo.estado(user));
    }

    @PostMapping("/consentimiento")
    public ConsentimientoOut aceptar(@Valid @RequestBody AceptarIn in,
                                     @AuthenticationPrincipal UsuarioActual user) {
        var antes = consentimiento.estado(user);
        var despues = consentimiento.aceptar(user, in.version());
        if (!antes.aceptado()) {
            auditoria.auditar(Accion.CONSENTIMIENTO_ACEPTADO, user, "usuario", user.id(),
                    Map.of("version", despues.version()));
        }
        return ConsentimientoOut.de(despues, verificacionCorreo.estado(user));
    }

    /** Borra las preguntas y respuestas guardadas de un expediente. Requiere ser su administrador. */
    @DeleteMapping("/expedientes/{expedienteId}/consultas")
    public ResponseEntity<Void> borrarHistorial(@PathVariable UUID expedienteId,
                                                @AuthenticationPrincipal UsuarioActual user) {
        autorizacion.obtener(user, expedienteId, Permiso.ADMIN);
        int borradas = privacidad.borrarHistorial(user.tenantId(), expedienteId);
        auditoria.auditar(Accion.HISTORIAL_BORRADO, user, "expediente", expedienteId, Map.of("consultas", borradas));
        return ResponseEntity.noContent().build();
    }

    /** Elimina la cuenta personal y todo su contenido. Pide la contrasena: es irreversible. */
    @PostMapping("/cuenta/eliminar")
    public ResponseEntity<Void> eliminarCuenta(@Valid @RequestBody EliminarCuentaIn in,
                                               @AuthenticationPrincipal UsuarioActual user) {
        var u = usuarios.findById(user.id()).orElseThrow();
        if (PasswordService.excedeLimite(in.password()) || !passwords.verificar(in.password(), u.getPasswordHash())) {
            throw new ApiException(HttpStatus.FORBIDDEN, "Contraseña incorrecta");
        }
        // Primero se audita (la auditoria sobrevive al tenant); despues se borra.
        auditoria.auditar(Accion.CUENTA_ELIMINADA, user, "tenant", user.tenantId(), Map.of());
        privacidad.eliminarCuentaPersonal(user.tenantId());
        return ResponseEntity.noContent().build();
    }
}

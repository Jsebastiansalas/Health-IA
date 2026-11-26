package co.medtender.api.compartir;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.compartir.ComparticionService.CompartidoConmigo;
import co.medtender.api.compartir.ComparticionService.Comparticion;
import co.medtender.api.domain.Permiso;
import co.medtender.api.expediente.AutorizacionExpediente;
import co.medtender.api.limites.Limitador;
import co.medtender.api.privacidad.ConsentimientoService;
import co.medtender.api.security.UsuarioActual;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/** Cuidadores: invitar y quitar (la dueña, con permiso ADMIN propio), aceptar y salir (el cuidador). */
@RestController
@RequestMapping("/api/v1")
public class ComparticionController {

    /** El correo admite espacios alrededor: se normaliza antes de validarlo y guardarlo. */
    public record Invitacion(@NotBlank @Email @Size(max = 150) String correo, @NotNull Permiso permiso) {
        public Invitacion {
            correo = ComparticionService.normalizarCorreo(correo);
        }
    }

    public record Aceptar(@NotBlank @Size(max = 200) String token) {}

    private final ComparticionService comparticiones;
    private final AutorizacionExpediente autorizacion;
    private final ConsentimientoService consentimiento;
    private final Limitador limitador;
    private final AuditoriaService auditoria;

    public ComparticionController(ComparticionService comparticiones, AutorizacionExpediente autorizacion,
                                  ConsentimientoService consentimiento, Limitador limitador, AuditoriaService auditoria) {
        this.comparticiones = comparticiones;
        this.autorizacion = autorizacion;
        this.consentimiento = consentimiento;
        this.limitador = limitador;
        this.auditoria = auditoria;
    }

    @PostMapping("/expedientes/{expedienteId}/comparticiones")
    @ResponseStatus(HttpStatus.CREATED)
    public Comparticion invitar(@PathVariable UUID expedienteId, @Valid @RequestBody Invitacion in,
                                @AuthenticationPrincipal UsuarioActual user) {
        autorizacion.obtener(user, expedienteId, Permiso.ADMIN);
        comparticiones.exigirCuentaPersonal(user);
        consentimiento.exigir(user);
        limitador.exigir("invitar_usuario", user.id().toString(), 10, 86400);
        Comparticion c = comparticiones.invitar(user, expedienteId, in.correo(), in.permiso());
        // Sin el correo invitado: la auditoría no se borra con la cuenta.
        auditoria.auditar(Accion.COMPARTICION_INVITADA, user, "expediente", expedienteId,
                Map.of("comparticion", c.id().toString(), "permiso", c.permiso().name()));
        return c;
    }

    @GetMapping("/expedientes/{expedienteId}/comparticiones")
    public List<Comparticion> listar(@PathVariable UUID expedienteId, @AuthenticationPrincipal UsuarioActual user) {
        autorizacion.obtener(user, expedienteId, Permiso.ADMIN);
        return comparticiones.listar(user, expedienteId);
    }

    @DeleteMapping("/expedientes/{expedienteId}/comparticiones/{comparticionId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void revocar(@PathVariable UUID expedienteId, @PathVariable UUID comparticionId,
                        @AuthenticationPrincipal UsuarioActual user) {
        autorizacion.obtener(user, expedienteId, Permiso.ADMIN);
        comparticiones.revocar(user, expedienteId, comparticionId);
    }

    @PostMapping("/invitaciones/aceptar")
    public CompartidoConmigo aceptar(@Valid @RequestBody Aceptar in, @AuthenticationPrincipal UsuarioActual user) {
        limitador.exigir("aceptar_invitacion", user.id().toString(), 10, 900);
        consentimiento.exigirCorreoVerificado(user);
        return comparticiones.aceptar(user, in.token());
    }

    @GetMapping("/compartidos")
    public List<CompartidoConmigo> compartidos(@AuthenticationPrincipal UsuarioActual user) {
        return comparticiones.compartidosConmigo(user);
    }

    @DeleteMapping("/compartidos/{expedienteId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void salir(@PathVariable UUID expedienteId, @AuthenticationPrincipal UsuarioActual user) {
        comparticiones.salir(user, expedienteId);
    }
}

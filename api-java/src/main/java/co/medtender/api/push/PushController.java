package co.medtender.api.push;

import co.medtender.api.limites.Limitador;
import co.medtender.api.security.UsuarioActual;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/** Avisos de recordatorios en el dispositivo, como complemento o alternativa del correo. */
@RestController
@RequestMapping("/api/v1/push")
public class PushController {

    public record Suscripcion(@NotBlank @Size(max = 1000) String endpoint) {}

    public record Preferencia(@NotNull Boolean porCorreo) {}

    private final PushService push;
    private final Limitador limitador;

    public PushController(PushService push, Limitador limitador) {
        this.push = push;
        this.limitador = limitador;
    }

    @GetMapping
    public PushService.Estado estado(@AuthenticationPrincipal UsuarioActual user) {
        return push.estado(user);
    }

    @PostMapping("/suscripciones")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void suscribir(@Valid @RequestBody Suscripcion in, @AuthenticationPrincipal UsuarioActual user) {
        limitador.exigir("push_suscribir", user.id().toString(), 30, 3600);
        push.suscribir(user, in.endpoint());
    }

    @DeleteMapping("/suscripciones")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void darDeBaja(@Valid @RequestBody Suscripcion in, @AuthenticationPrincipal UsuarioActual user) {
        push.darDeBaja(user, in.endpoint());
    }

    @PutMapping("/preferencia")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void preferencia(@Valid @RequestBody Preferencia in, @AuthenticationPrincipal UsuarioActual user) {
        push.preferirCorreo(user, in.porCorreo());
    }
}

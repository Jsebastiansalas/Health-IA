package co.medtender.api.privacidad;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.domain.Permiso;
import co.medtender.api.domain.TipoTenant;
import co.medtender.api.domain.UsuarioRepository;
import co.medtender.api.expediente.AutorizacionExpediente;
import co.medtender.api.limites.Limitador;
import co.medtender.api.security.PasswordService;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
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

    public record ExportarIn(@NotBlank String password) {}

    /** `meses` null: conservar todo. */
    public record RetencionIn(Integer meses) {}

    public record RetencionOut(Integer meses, Map<String, Integer> seBorrarian) {}

    public record RetencionCambiada(Integer meses, int borradas) {}

    public record EliminarCuentaIn(@NotBlank String password) {}

    private final ConsentimientoService consentimiento;
    private final PrivacidadService privacidad;
    private final AutorizacionExpediente autorizacion;
    private final AuditoriaService auditoria;
    private final UsuarioRepository usuarios;
    private final PasswordService passwords;
    private final VerificacionCorreoService verificacionCorreo;
    private final ExportacionService exportacion;
    private final Limitador limitador;
    private final RetencionService retencion;

    public PrivacidadController(ConsentimientoService consentimiento, PrivacidadService privacidad,
                                AutorizacionExpediente autorizacion, AuditoriaService auditoria,
                                UsuarioRepository usuarios, PasswordService passwords,
                                VerificacionCorreoService verificacionCorreo, ExportacionService exportacion,
                                Limitador limitador, RetencionService retencion) {
        this.retencion = retencion;
        this.exportacion = exportacion;
        this.limitador = limitador;
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

    @GetMapping("/cuenta/retencion")
    public RetencionOut retencion(@AuthenticationPrincipal UsuarioActual user) {
        exigirCuentaPersonal(user);
        return new RetencionOut(retencion.meses(user.tenantId()), retencion.seBorrarian(user.tenantId()));
    }

    /** Cuanto se conserva el historial. Lo que ya supera el plazo se borra en el momento. */
    @PutMapping("/cuenta/retencion")
    public RetencionCambiada elegirRetencion(@RequestBody RetencionIn in, @AuthenticationPrincipal UsuarioActual user) {
        exigirCuentaPersonal(user);
        if (in.meses() != null && !RetencionService.PLAZOS.contains(in.meses())) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "El plazo debe ser de 3, 6, 12 o 24 meses");
        }
        int borradas = retencion.elegir(user.tenantId(), in.meses());
        var detalle = new LinkedHashMap<String, Object>();
        detalle.put("meses", in.meses());
        detalle.put("borradas", borradas);
        auditoria.auditar(Accion.RETENCION_CAMBIADA, user, "tenant", user.tenantId(), detalle);
        return new RetencionCambiada(in.meses(), borradas);
    }

    private void exigirCuentaPersonal(UsuarioActual user) {
        if (consentimiento.tipoDe(user) != TipoTenant.PERSONAL) {
            throw new ApiException(HttpStatus.FORBIDDEN, "En una organización, esto lo gestiona su administrador");
        }
    }

    /**
     * «Descargar mis datos»: un ZIP con lo que hay de la cuenta personal. Pide la contraseña porque es todo junto;
     * se arma al pedirlo y no se guarda. En una organización los datos son de la institución.
     */
    @PostMapping("/cuenta/exportar")
    public ResponseEntity<byte[]> exportar(@Valid @RequestBody ExportarIn in, @AuthenticationPrincipal UsuarioActual user) {
        exigirCuentaPersonal(user);
        limitador.exigir("exportar_intento", user.id().toString(), 10, 3600);
        exigirContrasena(user, in.password());
        limitador.exigir("exportar", user.id().toString(), 3, 3600);
        var r = exportacion.exportar(user.tenantId(), user.id());
        auditoria.auditar(Accion.DATOS_EXPORTADOS, user, "tenant", user.tenantId(), r.conteos());
        String nombre = "medtender-mis-datos-" + LocalDate.now(ZoneId.of("America/Bogota")) + ".zip";
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_TYPE, "application/zip")
                .header(HttpHeaders.CACHE_CONTROL, "no-store")
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + nombre + "\"")
                .body(r.zip());
    }

    private void exigirContrasena(UsuarioActual user, String password) {
        var u = usuarios.findById(user.id()).orElseThrow();
        if (PasswordService.excedeLimite(password) || !passwords.verificar(password, u.getPasswordHash())) {
            throw new ApiException(HttpStatus.FORBIDDEN, "Contraseña incorrecta");
        }
    }

    /** Elimina la cuenta personal y todo su contenido. Pide la contrasena: es irreversible. */
    @PostMapping("/cuenta/eliminar")
    public ResponseEntity<Void> eliminarCuenta(@Valid @RequestBody EliminarCuentaIn in,
                                               @AuthenticationPrincipal UsuarioActual user) {
        exigirContrasena(user, in.password());
        // Primero se audita (la auditoria sobrevive al tenant); despues se borra.
        auditoria.auditar(Accion.CUENTA_ELIMINADA, user, "tenant", user.tenantId(), Map.of());
        privacidad.eliminarCuentaPersonal(user.tenantId());
        return ResponseEntity.noContent().build();
    }
}

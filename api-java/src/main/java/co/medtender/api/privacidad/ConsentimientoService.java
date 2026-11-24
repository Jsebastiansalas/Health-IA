package co.medtender.api.privacidad;

import co.medtender.api.domain.Consentimiento;
import co.medtender.api.domain.ConsentimientoRepository;
import co.medtender.api.domain.TenantRepository;
import co.medtender.api.domain.TipoTenant;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import java.time.Instant;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Consentimiento informado para tratar documentos de salud. Las cuentas PERSONALES (pacientes y familias)
 * deben aceptar el texto vigente antes de subir documentos o consultar; en una organizacion lo gestiona
 * la institucion, asi que no se exige a sus usuarios.
 */
@Service
public class ConsentimientoService {

    /**
     * Cambiar el texto de consentimiento exige subir esta version: todos deben aceptarlo de nuevo.
     * v2: el texto pasa a decir que los datos personales se enmascaran antes de enviarlos al proveedor.
     * v3: pruebas cerradas con la versión gratuita de Gemini, respaldos de 14 días, registro de accesos sin
     * vencimiento, documentos de terceros y menores, y responsable del tratamiento.
     */
    public static final String VERSION_VIGENTE = "2026-11-v3";

    public record Estado(String version, boolean requerido, boolean aceptado, Instant aceptadoAt, TipoTenant tipoCuenta) {}

    private final ConsentimientoRepository consentimientos;
    private final TenantRepository tenants;
    private final VerificacionCorreoService verificacionCorreo;

    public ConsentimientoService(ConsentimientoRepository consentimientos, TenantRepository tenants,
                                 VerificacionCorreoService verificacionCorreo) {
        this.consentimientos = consentimientos;
        this.tenants = tenants;
        this.verificacionCorreo = verificacionCorreo;
    }

    @Transactional(readOnly = true)
    public Estado estado(UsuarioActual u) {
        TipoTenant tipo = tenants.findById(u.tenantId()).map(t -> t.getTipo()).orElse(TipoTenant.ORGANIZACION);
        var aceptado = consentimientos.findByUsuarioIdAndVersion(u.id(), VERSION_VIGENTE);
        return new Estado(VERSION_VIGENTE, tipo == TipoTenant.PERSONAL, aceptado.isPresent(),
                aceptado.map(Consentimiento::getAceptadoAt).orElse(null), tipo);
    }

    /** Idempotente: aceptar dos veces la misma version no crea otra fila. */
    @Transactional
    public Estado aceptar(UsuarioActual u) {
        if (consentimientos.findByUsuarioIdAndVersion(u.id(), VERSION_VIGENTE).isEmpty()) {
            consentimientos.saveAndFlush(new Consentimiento(u.tenantId(), u.id(), VERSION_VIGENTE));
        }
        return estado(u);
    }

    /** 403 con codigo estable para que la interfaz muestre el consentimiento en lugar de un error generico. */
    public void exigir(UsuarioActual u) {
        verificacionCorreo.exigir(u); // las cuentas personales confirman su correo antes que nada
        Estado e = estado(u);
        if (e.requerido() && !e.aceptado()) {
            throw new ApiException(HttpStatus.FORBIDDEN,
                    "Debes aceptar el consentimiento para usar tus documentos de salud con el asistente",
                    Map.of("codigo", "consentimiento_requerido", "version", VERSION_VIGENTE));
        }
    }
}

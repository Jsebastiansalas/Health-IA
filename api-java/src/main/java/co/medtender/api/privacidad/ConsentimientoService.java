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

/**
 * Consentimiento informado para tratar documentos de salud. Las cuentas PERSONALES (pacientes y familias)
 * deben aceptar el texto vigente antes de subir documentos o consultar; en una organizacion lo gestiona
 * la institucion, asi que no se exige a sus usuarios.
 */
@Service
public class ConsentimientoService {

    /**
     * El texto depende del proveedor de IA que el agente tiene activo, y cada texto tiene su version: cambiar
     * de proveedor obliga a aceptar de nuevo. Cambiar un texto exige subir sus versiones.
     * v2: el texto pasa a decir que los datos personales se enmascaran antes de enviarlos al proveedor.
     * v3: API gratuita de Gemini (puede usar lo que recibe), respaldos de 14 días, registro de accesos sin
     * vencimiento, documentos de terceros y menores, y responsable del tratamiento.
     * v4: retirada; decia Vertex AI sin mirar el proveedor configurado.
     * v5: Gemini en Google Cloud (Vertex AI), sin entrenamiento con los datos.
     * El sufijo -claude indica que ademas Claude (Anthropic) responde si el principal falla.
     */
    private static final String VERSION_GEMINI_API = "2026-11-v3";
    private static final String VERSION_VERTEX = "2026-11-v5";

    static String version(ProveedorIaService.Proveedor p) {
        String base = p.principal().equals("vertex") ? VERSION_VERTEX : VERSION_GEMINI_API;
        return p.respaldo().isEmpty() ? base : base + "-" + p.respaldo();
    }

    public record Estado(String version, boolean requerido, boolean aceptado, Instant aceptadoAt, TipoTenant tipoCuenta,
                         String proveedorIa, String respaldoIa) {}

    private final ConsentimientoRepository consentimientos;
    private final TenantRepository tenants;
    private final VerificacionCorreoService verificacionCorreo;
    private final ProveedorIaService proveedores;

    public ConsentimientoService(ConsentimientoRepository consentimientos, TenantRepository tenants,
                                 VerificacionCorreoService verificacionCorreo, ProveedorIaService proveedores) {
        this.consentimientos = consentimientos;
        this.tenants = tenants;
        this.verificacionCorreo = verificacionCorreo;
        this.proveedores = proveedores;
    }

    /** Sin transaccion propia: preguntar por el proveedor no debe retener una conexion a la base. */
    public Estado estado(UsuarioActual u) {
        TipoTenant tipo = tipoDe(u);
        boolean requerido = tipo == TipoTenant.PERSONAL;
        var proveedor = proveedores.actual().orElse(null);
        if (proveedor == null) {
            if (requerido) {
                throw sinProveedor();
            }
            return new Estado("", false, false, null, tipo, "", "");
        }
        String version = version(proveedor);
        var aceptado = consentimientos.findByUsuarioIdAndVersion(u.id(), version);
        return new Estado(version, requerido, aceptado.isPresent(),
                aceptado.map(Consentimiento::getAceptadoAt).orElse(null), tipo, proveedor.principal(), proveedor.respaldo());
    }

    /**
     * Registra la aceptacion del texto que la persona tenia en pantalla: si el proveedor cambio entretanto,
     * se rechaza para que lea el nuevo. Idempotente: aceptar dos veces la misma version no crea otra fila.
     */
    public Estado aceptar(UsuarioActual u, String versionVista) {
        Estado e = estado(u);
        if (e.version().isEmpty()) {
            throw sinProveedor();
        }
        if (!e.version().equals(versionVista)) {
            throw new ApiException(HttpStatus.CONFLICT,
                    "El texto del consentimiento cambió. Léelo de nuevo antes de aceptar.",
                    Map.of("codigo", "consentimiento_cambio", "version", e.version()));
        }
        if (!e.aceptado()) {
            consentimientos.saveAndFlush(new Consentimiento(u.tenantId(), u.id(), e.version()));
        }
        return estado(u);
    }

    /** 403 con codigo estable para que la interfaz muestre el consentimiento en lugar de un error generico. */
    public void exigir(UsuarioActual u) {
        verificacionCorreo.exigir(u); // las cuentas personales confirman su correo antes que nada
        if (tipoDe(u) != TipoTenant.PERSONAL) {
            return;
        }
        Estado e = estado(u);
        if (!e.aceptado()) {
            throw new ApiException(HttpStatus.FORBIDDEN,
                    "Debes aceptar el consentimiento para usar tus documentos de salud con el asistente",
                    Map.of("codigo", "consentimiento_requerido", "version", e.version()));
        }
    }

    public TipoTenant tipoDe(UsuarioActual u) {
        return tenants.findById(u.tenantId()).map(t -> t.getTipo()).orElse(TipoTenant.ORGANIZACION);
    }

    private static ApiException sinProveedor() {
        return new ApiException(HttpStatus.SERVICE_UNAVAILABLE,
                "No pudimos comprobar qué servicio de inteligencia artificial está activo. Intenta de nuevo en un momento.");
    }
}

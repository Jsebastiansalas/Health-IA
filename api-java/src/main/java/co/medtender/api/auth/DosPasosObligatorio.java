package co.medtender.api.auth;

import co.medtender.api.domain.TenantRepository;
import co.medtender.api.domain.TipoTenant;
import co.medtender.api.domain.Usuario;
import co.medtender.api.domain.UsuarioRepository;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.Map;
import java.util.Set;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Con {@code medtender.seguridad.dos-pasos-admins=true}, un administrador de una organización sin verificación en
 * dos pasos solo puede usar lo necesario para activarla: el resto de la API responde 403 con el código
 * {@code dos_pasos_requerido} y la interfaz lo lleva a «Seguridad de la cuenta».
 */
@Configuration
public class DosPasosObligatorio implements WebMvcConfigurer, HandlerInterceptor {

    private static final Set<String> PERMITIDAS = Set.of(
            "/api/v1/auth/me", "/api/v1/auth/2fa", "/api/v1/auth/2fa/iniciar", "/api/v1/auth/2fa/activar",
            "/api/v1/auth/logout", "/api/v1/auth/cerrar-sesiones", "/api/v1/auth/cambiar-contrasena", "/api/v1/consentimiento");

    private final boolean obligatoria;
    private final UsuarioRepository usuarios;
    private final TenantRepository tenants;

    public DosPasosObligatorio(@Value("${medtender.seguridad.dos-pasos-admins:false}") boolean obligatoria,
                               UsuarioRepository usuarios, TenantRepository tenants) {
        this.obligatoria = obligatoria;
        this.usuarios = usuarios;
        this.tenants = tenants;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(this).addPathPatterns("/api/v1/**");
    }

    @Override
    public boolean preHandle(HttpServletRequest req, HttpServletResponse res, Object handler) {
        if (!obligatoria || PERMITIDAS.contains(req.getRequestURI())) return true;
        var auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof UsuarioActual u) || !u.esAdminTenant()) return true;
        boolean organizacion = tenants.findById(u.tenantId()).map(t -> t.getTipo() == TipoTenant.ORGANIZACION).orElse(false);
        boolean activa = usuarios.findById(u.id()).map(Usuario::isTotpActivo).orElse(false);
        if (organizacion && !activa) {
            throw new ApiException(HttpStatus.FORBIDDEN,
                    "Como administrador de la organización debes activar la verificación en dos pasos",
                    Map.of("codigo", "dos_pasos_requerido"));
        }
        return true;
    }
}

package co.medtender.api.web;

import co.medtender.api.config.MedtenderProperties;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Protege /metrics con un token (Authorization: Bearer ...). Sin token configurado el endpoint
 * queda deshabilitado (404). Se instancia dentro de la cadena de seguridad, no como bean global.
 */
public class MetricsTokenFilter extends OncePerRequestFilter {

    private final MedtenderProperties props;

    public MetricsTokenFilter(MedtenderProperties props) {
        this.props = props;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest req) {
        return !req.getRequestURI().equals("/metrics");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse resp, FilterChain chain)
            throws ServletException, IOException {
        String esperado = props.metricsToken();
        if (esperado == null || esperado.isBlank()) {
            RespuestaError.escribir(resp, 404, "No encontrado");
            return;
        }
        String cabecera = req.getHeader("Authorization");
        String recibido = cabecera != null && cabecera.startsWith("Bearer ") ? cabecera.substring(7) : "";
        boolean ok = MessageDigest.isEqual(recibido.getBytes(StandardCharsets.UTF_8), esperado.getBytes(StandardCharsets.UTF_8));
        if (!ok) {
            resp.setHeader("WWW-Authenticate", "Bearer");
            RespuestaError.escribir(resp, 401, "Token de métricas inválido");
            return;
        }
        chain.doFilter(req, resp);
    }
}

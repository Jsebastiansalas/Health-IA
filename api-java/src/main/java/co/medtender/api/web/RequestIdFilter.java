package co.medtender.api.web;

import co.medtender.api.config.MedtenderProperties;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.UUID;
import java.util.regex.Pattern;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Primer filtro de la cadena: identificador de peticion (X-Request-ID), IP real del cliente, contexto
 * de logs (MDC), Cache-Control: no-store en la API y una linea de log de acceso.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class RequestIdFilter extends OncePerRequestFilter {

    private static final Logger acceso = LoggerFactory.getLogger("medtender.acceso");
    private static final Pattern ID_VALIDO = Pattern.compile("^[A-Za-z0-9._-]{1,64}$");

    private final MedtenderProperties props;

    public RequestIdFilter(MedtenderProperties props) {
        this.props = props;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse resp, FilterChain chain)
            throws ServletException, IOException {
        String entrante = req.getHeader("X-Request-ID");
        String id = entrante != null && ID_VALIDO.matcher(entrante).matches()
                ? entrante
                : UUID.randomUUID().toString().replace("-", "");
        String ip = ipCliente(req);
        MDC.put("request_id", id);
        MDC.put("ip", ip);
        resp.setHeader("X-Request-ID", id);
        String ruta = req.getRequestURI();
        if (ruta.startsWith("/api/")) {
            resp.setHeader("Cache-Control", "no-store");
        }
        long inicio = System.nanoTime();
        try {
            chain.doFilter(req, resp);
        } finally {
            if (!ruta.equals("/metrics") && !ruta.startsWith("/health")) {
                long ms = (System.nanoTime() - inicio) / 1_000_000;
                acceso.info("{} {} -> {} ({} ms)", req.getMethod(), ruta, resp.getStatus(), ms);
            }
            MDC.clear();
        }
    }

    /** Detras de Caddy la IP real es la ultima de X-Forwarded-For (la que anade el proxy de confianza). */
    private String ipCliente(HttpServletRequest req) {
        if (props.confiarProxy()) {
            String xff = req.getHeader("X-Forwarded-For");
            if (xff != null && !xff.isBlank()) {
                String[] partes = xff.split(",");
                return partes[partes.length - 1].trim();
            }
        }
        return req.getRemoteAddr();
    }
}

package co.medtender.api.web;

import co.medtender.api.config.MedtenderProperties;
import co.medtender.api.limites.Limitador;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/** Limite general por IP para toda la API (excepto /health y /metrics). */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 1)
public class LimiteGeneralFilter extends OncePerRequestFilter {

    private final Limitador limitador;
    private final MedtenderProperties props;

    public LimiteGeneralFilter(Limitador limitador, MedtenderProperties props) {
        this.limitador = limitador;
        this.props = props;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest req) {
        String ruta = req.getRequestURI();
        return ruta.equals("/metrics") || ruta.startsWith("/health");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse resp, FilterChain chain)
            throws ServletException, IOException {
        var r = limitador.golpear("general", String.valueOf(MDC.get("ip")), props.rateLimit().generalIpMin(), 60);
        if (!r.permitido()) {
            limitador.rechazar("general", r.reintentarEnS());
            resp.setHeader("Retry-After", Integer.toString(r.reintentarEnS()));
            RespuestaError.escribir(resp, 429,
                    "Demasiadas solicitudes. Intente de nuevo en " + r.reintentarEnS() + " s.");
            return;
        }
        chain.doFilter(req, resp);
    }
}

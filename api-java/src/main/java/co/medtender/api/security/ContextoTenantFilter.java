package co.medtender.api.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import org.springframework.web.filter.OncePerRequestFilter;

/** Garantiza que el contexto de tenant de una peticion nunca sobreviva a ella en la hebra. */
public class ContextoTenantFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        ContextoTenant.limpiar();
        try {
            chain.doFilter(request, response);
        } finally {
            ContextoTenant.limpiar();
        }
    }

    @Configuration
    static class Registro {
        @Bean
        FilterRegistrationBean<ContextoTenantFilter> contextoTenantFilter() {
            var r = new FilterRegistrationBean<>(new ContextoTenantFilter());
            r.setOrder(Ordered.HIGHEST_PRECEDENCE);
            return r;
        }
    }
}

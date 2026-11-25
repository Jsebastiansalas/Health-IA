package co.medtender.api.config;

import co.medtender.api.security.ConversorUsuario;
import co.medtender.api.security.JwtService;
import co.medtender.api.web.MetricsTokenFilter;
import co.medtender.api.web.RespuestaError;
import java.util.List;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.server.resource.web.authentication.BearerTokenAuthenticationFilter;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.security.web.access.intercept.AuthorizationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class SecurityConfig {

    /** /health y /metrics: sin JWT de usuario. /metrics exige su propio token. */
    @Bean
    @Order(1)
    SecurityFilterChain operacion(HttpSecurity http, MedtenderProperties props) throws Exception {
        http.securityMatcher("/health", "/health/**", "/metrics")
                .csrf(AbstractHttpConfigurer::disable)
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(a -> a.anyRequest().permitAll())
                .addFilterBefore(new MetricsTokenFilter(props), AuthorizationFilter.class);
        return http.build();
    }

    @Bean
    @Order(2)
    SecurityFilterChain api(HttpSecurity http, JwtDecoder decoder, ConversorUsuario conversor,
                            MedtenderProperties props) throws Exception {
        http.cors(c -> c.configurationSource(configuracionCors(props)))
                .csrf(AbstractHttpConfigurer::disable) // API stateless con Bearer: sin cookies, sin CSRF
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(a -> a
                        .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/v1/publico/ia").permitAll()
                        .requestMatchers(HttpMethod.POST, "/api/v1/auth/login", "/api/v1/auth/refresh",
                                "/api/v1/auth/registro-tenant", "/api/v1/auth/registro-personal",
                                "/api/v1/auth/verificar-correo", "/api/v1/auth/logout",
                                "/api/v1/auth/olvide-contrasena", "/api/v1/auth/restablecer-contrasena",
                                "/api/v1/auth/2fa/verificar").permitAll()
                        .anyRequest().authenticated())
                .oauth2ResourceServer(o -> o
                        .jwt(j -> j.decoder(decoder).jwtAuthenticationConverter(conversor))
                        .authenticationEntryPoint(puntoEntrada()))
                .exceptionHandling(e -> e
                        .authenticationEntryPoint(puntoEntrada())
                        .accessDeniedHandler(accesoDenegado()));
        return http.build();
    }

    @Bean
    JwtDecoder jwtDecoder(JwtService jwt) {
        return jwt.decoder();
    }

    // No es un bean: Spring MVC ya registra el suyo (mvcHandlerMappingIntrospector) y chocarian.
    private static CorsConfigurationSource configuracionCors(MedtenderProperties props) {
        CorsConfiguration c = new CorsConfiguration();
        c.setAllowedOrigins(props.corsOrigins());
        c.setAllowedMethods(List.of("GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"));
        c.setAllowedHeaders(List.of("Authorization", "Content-Type", "X-Request-ID"));
        c.setExposedHeaders(List.of("X-Request-ID", "Retry-After"));
        c.setMaxAge(600L);
        UrlBasedCorsConfigurationSource fuente = new UrlBasedCorsConfigurationSource();
        fuente.registerCorsConfiguration("/**", c);
        return fuente;
    }

    private static AuthenticationEntryPoint puntoEntrada() {
        return (req, resp, ex) -> {
            boolean sinToken = req.getHeader("Authorization") == null;
            String detalle = sinToken
                    ? "No autenticado"
                    : ConversorUsuario.USUARIO_INACTIVO.equals(ex.getMessage())
                            ? ConversorUsuario.USUARIO_INACTIVO
                            : "Token inválido o expirado";
            resp.setHeader("WWW-Authenticate", "Bearer");
            RespuestaError.escribir(resp, 401, detalle);
        };
    }

    private static AccessDeniedHandler accesoDenegado() {
        return (req, resp, ex) -> RespuestaError.escribir(resp, 403, "Rol sin autorización");
    }
}

package co.medtender.api.security;

import co.medtender.api.domain.Usuario;
import co.medtender.api.domain.UsuarioRepository;
import java.util.List;
import java.util.UUID;
import org.slf4j.MDC;
import org.springframework.core.convert.converter.Converter;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.InvalidBearerTokenException;
import org.springframework.stereotype.Component;

/**
 * Convierte el JWT validado en la identidad de la peticion. Se consulta la base de datos en cada
 * solicitud para que la desactivacion o el cambio de rol surtan efecto de inmediato, aunque el
 * token siga vigente.
 */
@Component
public class ConversorUsuario implements Converter<Jwt, AbstractAuthenticationToken> {

    public static final String USUARIO_INACTIVO = "Usuario inactivo o inexistente";

    private final UsuarioRepository usuarios;

    public ConversorUsuario(UsuarioRepository usuarios) {
        this.usuarios = usuarios;
    }

    @Override
    public AbstractAuthenticationToken convert(Jwt jwt) {
        if (!JwtService.Tipo.ACCESS.valor().equals(jwt.getClaimAsString("type"))) {
            throw new InvalidBearerTokenException("Token inválido o expirado");
        }
        UUID id;
        UUID tenantId;
        try {
            id = UUID.fromString(jwt.getSubject());
            tenantId = UUID.fromString(jwt.getClaimAsString("tenant_id"));
        } catch (IllegalArgumentException | NullPointerException e) {
            throw new InvalidBearerTokenException("Token inválido o expirado");
        }
        // El claim esta firmado: es fuente confiable del tenant. Se fija ANTES de consultar para que
        // la base (RLS) solo entregue filas de esa organizacion durante el resto de la peticion.
        ContextoTenant.fijarTenant(tenantId);
        Usuario u = usuarios.findByIdAndTenantId(id, tenantId)
                .filter(Usuario::isActivo)
                .orElseThrow(() -> new InvalidBearerTokenException(USUARIO_INACTIVO));
        // Desde aqui, cada log de la peticion lleva el usuario y el tenant.
        MDC.put("usuario_id", u.getId().toString());
        MDC.put("tenant_id", u.getTenantId().toString());
        var actual = new UsuarioActual(u.getId(), u.getTenantId(), u.getRolGlobal(), u.getEmail());
        return new UsernamePasswordAuthenticationToken(
                actual, jwt.getTokenValue(), List.of(new SimpleGrantedAuthority("ROLE_" + u.getRolGlobal().name())));
    }
}

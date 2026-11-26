package co.medtender.api.security;

import co.medtender.api.config.MedtenderProperties;
import co.medtender.api.domain.RolGlobal;
import com.nimbusds.jose.jwk.source.ImmutableSecret;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.UUID;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.BadJwtException;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;
import org.springframework.stereotype.Service;

/**
 * Emision y lectura de JWT HS256 con los mismos claims que usaba el servicio Python
 * (sub, tenant_id, rol, type, iat, exp, jti): los tokens ya emitidos siguen siendo validos.
 */
@Service
public class JwtService {

    public enum Tipo {
        ACCESS("access"),
        REFRESH("refresh"),
        /** Desafío de 5 minutos entre la contraseña correcta y el código de verificación en dos pasos. */
        DOS_PASOS("2fa");

        private final String valor;

        Tipo(String valor) {
            this.valor = valor;
        }

        public String valor() {
            return valor;
        }
    }

    private final MedtenderProperties props;
    private final JwtEncoder encoder;
    private final JwtDecoder decoder;

    public JwtService(MedtenderProperties props) {
        this.props = props;
        byte[] clave = props.jwt().secret() == null ? new byte[0] : props.jwt().secret().getBytes(StandardCharsets.UTF_8);
        if (clave.length < 32) {
            throw new IllegalStateException("JWT_SECRET debe tener al menos 32 caracteres");
        }
        SecretKey secreto = new SecretKeySpec(clave, "HmacSHA256");
        this.encoder = new NimbusJwtEncoder(new ImmutableSecret<>(secreto));
        this.decoder = NimbusJwtDecoder.withSecretKey(secreto).macAlgorithm(MacAlgorithm.HS256).build();
    }

    public JwtDecoder decoder() {
        return decoder;
    }

    /** Token emitido con su identificador (jti) y su vencimiento, para registrar la sesión. */
    public record Emitido(String token, String jti, Instant expira) {}

    public String crear(UUID usuarioId, UUID tenantId, RolGlobal rol, Tipo tipo) {
        return emitir(usuarioId, tenantId, rol, tipo, null).token();
    }

    /**
     * Emite un token. El refresh lleva la `familia` (el inicio de sesión al que pertenece) para poder revocar
     * todas sus renovaciones si una se reutiliza.
     */
    public Emitido emitir(UUID usuarioId, UUID tenantId, RolGlobal rol, Tipo tipo, UUID familia) {
        Instant ahora = Instant.now();
        Duration ttl = switch (tipo) {
            case ACCESS -> Duration.ofMinutes(props.jwt().accessMinutes());
            case REFRESH -> Duration.ofDays(props.jwt().refreshDays());
            case DOS_PASOS -> Duration.ofMinutes(5);
        };
        String jti = UUID.randomUUID().toString().replace("-", "");
        var b = JwtClaimsSet.builder()
                .subject(usuarioId.toString())
                .claim("tenant_id", tenantId.toString())
                .claim("rol", rol.name())
                .claim("type", tipo.valor())
                .issuedAt(ahora)
                .expiresAt(ahora.plus(ttl))
                .id(jti)
                // Milisegundos de emisión: el `iat` estándar va en segundos y no alcanza para invalidar sesiones.
                .claim("emitido_ms", ahora.toEpochMilli());
        if (familia != null) b.claim("fam", familia.toString());
        JwsHeader cabecera = JwsHeader.with(MacAlgorithm.HS256).build();
        String token = encoder.encode(JwtEncoderParameters.from(cabecera, b.build())).getTokenValue();
        return new Emitido(token, jti, ahora.plus(ttl));
    }

    /** Momento de emisión con milisegundos (o el `iat` en tokens antiguos sin `emitido_ms`). */
    public static Instant emitido(Jwt jwt) {
        Object ms = jwt.getClaims().get("emitido_ms");
        if (ms instanceof Number n) return Instant.ofEpochMilli(n.longValue());
        return jwt.getIssuedAt();
    }

    /** Valida firma, expiracion, tipo y claims obligatorios. Lanza {@link BadJwtException} si algo falla. */
    public Jwt leer(String token, Tipo esperado) {
        Jwt jwt = decoder.decode(token);
        if (jwt.getSubject() == null || jwt.getClaimAsString("tenant_id") == null) {
            throw new BadJwtException("Faltan claims obligatorios");
        }
        if (!esperado.valor().equals(jwt.getClaimAsString("type"))) {
            throw new BadJwtException("Tipo de token incorrecto");
        }
        return jwt;
    }
}

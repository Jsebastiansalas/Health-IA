package co.medtender.api.push;

import java.math.BigInteger;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.AlgorithmParameters;
import java.security.GeneralSecurityException;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.Signature;
import java.security.spec.ECGenParameterSpec;
import java.security.spec.ECParameterSpec;
import java.security.spec.ECPrivateKeySpec;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;

/** Identificacion del servidor ante el servicio de push (VAPID, RFC 8292): un JWT ES256 por destino. */
public final class Vapid {

    private static final Base64.Encoder B64 = Base64.getUrlEncoder().withoutPadding();

    private final String publica;
    private final PrivateKey privada;
    private final String contacto;

    /** Claves en base64url sin relleno: la publica son 65 bytes (punto sin comprimir) y la privada 32. */
    public Vapid(String publica, String privada, String contacto) {
        try {
            byte[] punto = Base64.getUrlDecoder().decode(publica);
            byte[] escalar = Base64.getUrlDecoder().decode(privada);
            if (punto.length != 65 || punto[0] != 4 || escalar.length != 32) {
                throw new IllegalArgumentException("Claves VAPID con formato inesperado");
            }
            var parametros = AlgorithmParameters.getInstance("EC");
            parametros.init(new ECGenParameterSpec("secp256r1"));
            this.privada = KeyFactory.getInstance("EC").generatePrivate(
                    new ECPrivateKeySpec(new BigInteger(1, escalar), parametros.getParameterSpec(ECParameterSpec.class)));
            this.publica = publica;
            this.contacto = contacto;
        } catch (GeneralSecurityException e) {
            throw new IllegalArgumentException("No se pudieron leer las claves VAPID", e);
        }
    }

    public String clavePublica() {
        return publica;
    }

    public String autorizacion(URI destino, Instant ahora) {
        String origen = destino.getScheme() + "://" + destino.getHost();
        String sinFirmar = texto("{\"typ\":\"JWT\",\"alg\":\"ES256\"}") + "." + texto(
                "{\"aud\":\"" + escapar(origen) + "\",\"exp\":" + ahora.plus(Duration.ofHours(12)).getEpochSecond()
                        + ",\"sub\":\"" + escapar(contacto) + "\"}");
        try {
            Signature firma = Signature.getInstance("SHA256withECDSAinP1363Format");
            firma.initSign(privada);
            firma.update(sinFirmar.getBytes(StandardCharsets.US_ASCII));
            return "vapid t=" + sinFirmar + "." + B64.encodeToString(firma.sign()) + ", k=" + publica;
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("No se pudo firmar la notificacion", e);
        }
    }

    private static String texto(String s) {
        return B64.encodeToString(s.getBytes(StandardCharsets.UTF_8));
    }

    private static String escapar(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}

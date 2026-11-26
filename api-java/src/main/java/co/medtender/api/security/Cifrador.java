package co.medtender.api.security;

import co.medtender.api.config.MedtenderProperties;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Base64;
import javax.crypto.Cipher;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Cifrado AES-256-GCM de secretos pequeños que se guardan en la base (p. ej. el secreto TOTP). La clave vive fuera
 * de la base: {@code CIFRADO_CLAVE} (32 bytes en base64). Sin ella se deriva de JWT_SECRET con una etiqueta propia,
 * lo que sirve en desarrollo; en producción conviene una clave aparte para poder rotar una sin la otra.
 */
@Component
public class Cifrador {

    private static final Logger log = LoggerFactory.getLogger(Cifrador.class);
    private static final SecureRandom ALEATORIO = new SecureRandom();
    private static final int IV = 12;
    private static final int ETIQUETA_BITS = 128;

    private final SecretKey clave;

    public Cifrador(@Value("${medtender.cifrado.clave:}") String claveBase64, MedtenderProperties props) {
        byte[] bytes;
        if (claveBase64 != null && !claveBase64.isBlank()) {
            bytes = Base64.getDecoder().decode(claveBase64.strip());
            if (bytes.length != 32) throw new IllegalStateException("CIFRADO_CLAVE debe ser de 32 bytes en base64");
        } else {
            if ("produccion".equalsIgnoreCase(props.entorno())) {
                log.warn("CIFRADO_CLAVE no está definida: se deriva de JWT_SECRET. Define una clave propia en producción.");
            }
            bytes = sha256("medtender-cifrado-v1|" + props.jwt().secret());
        }
        this.clave = new SecretKeySpec(bytes, "AES");
    }

    private static byte[] sha256(String s) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(s.getBytes(StandardCharsets.UTF_8));
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException(e);
        }
    }

    public String cifrar(String texto) {
        try {
            byte[] iv = new byte[IV];
            ALEATORIO.nextBytes(iv);
            Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
            c.init(Cipher.ENCRYPT_MODE, clave, new GCMParameterSpec(ETIQUETA_BITS, iv));
            byte[] cifrado = c.doFinal(texto.getBytes(StandardCharsets.UTF_8));
            return "v1:" + Base64.getEncoder().encodeToString(ByteBuffer.allocate(IV + cifrado.length).put(iv).put(cifrado).array());
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("No se pudo cifrar", e);
        }
    }

    public String descifrar(String valor) {
        if (valor == null || !valor.startsWith("v1:")) throw new IllegalArgumentException("Formato de cifrado desconocido");
        try {
            byte[] todo = Base64.getDecoder().decode(valor.substring(3));
            Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
            c.init(Cipher.DECRYPT_MODE, clave, new GCMParameterSpec(ETIQUETA_BITS, todo, 0, IV));
            return new String(c.doFinal(todo, IV, todo.length - IV), StandardCharsets.UTF_8);
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("No se pudo descifrar", e);
        }
    }
}

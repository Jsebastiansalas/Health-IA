package co.medtender.api.auth;

import java.net.URLEncoder;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Instant;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/**
 * Códigos de un solo uso por tiempo (TOTP, RFC 6238): HMAC-SHA1, 6 dígitos, pasos de 30 s. Compatible con Google
 * Authenticator, Microsoft Authenticator, 1Password y similares. Se acepta un paso de desfase a cada lado.
 */
public final class Totp {

    private static final SecureRandom ALEATORIO = new SecureRandom();
    private static final String BASE32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
    private static final int PASO_S = 30;

    private Totp() {}

    /** Secreto nuevo de 160 bits en base32 (lo que se guarda, cifrado, y lo que escanea la app). */
    public static String nuevoSecreto() {
        byte[] b = new byte[20];
        ALEATORIO.nextBytes(b);
        return base32(b);
    }

    public static String uri(String secreto, String cuenta) {
        String etiqueta = URLEncoder.encode("MedTender:" + cuenta, StandardCharsets.UTF_8).replace("+", "%20");
        return "otpauth://totp/" + etiqueta + "?secret=" + secreto + "&issuer=MedTender&algorithm=SHA1&digits=6&period=30";
    }

    public static boolean valido(String secreto, String codigo, Instant ahora) {
        if (codigo == null) return false;
        String c = codigo.replaceAll("\\s", "");
        if (!c.matches("\\d{6}")) return false;
        long paso = ahora.getEpochSecond() / PASO_S;
        byte[] clave = desdeBase32(secreto);
        boolean ok = false;
        for (long d = -1; d <= 1; d++) {
            // Sin cortar el bucle: el tiempo de respuesta no revela en qué paso coincidió.
            ok |= MessageDigest.isEqual(codigo(clave, paso + d).getBytes(StandardCharsets.US_ASCII), c.getBytes(StandardCharsets.US_ASCII));
        }
        return ok;
    }

    static String codigo(byte[] clave, long paso) {
        try {
            Mac mac = Mac.getInstance("HmacSHA1");
            mac.init(new SecretKeySpec(clave, "HmacSHA1"));
            byte[] h = mac.doFinal(ByteBuffer.allocate(8).putLong(paso).array());
            int o = h[h.length - 1] & 0x0f;
            int n = ((h[o] & 0x7f) << 24) | ((h[o + 1] & 0xff) << 16) | ((h[o + 2] & 0xff) << 8) | (h[o + 3] & 0xff);
            return String.format("%06d", n % 1_000_000);
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException(e);
        }
    }

    /** Código vigente (para pruebas). */
    public static String codigoActual(String secreto, Instant ahora) {
        return codigo(desdeBase32(secreto), ahora.getEpochSecond() / PASO_S);
    }

    static String base32(byte[] datos) {
        StringBuilder sb = new StringBuilder();
        int buffer = 0, bits = 0;
        for (byte b : datos) {
            buffer = (buffer << 8) | (b & 0xff);
            bits += 8;
            while (bits >= 5) {
                sb.append(BASE32.charAt((buffer >> (bits - 5)) & 31));
                bits -= 5;
            }
        }
        if (bits > 0) sb.append(BASE32.charAt((buffer << (5 - bits)) & 31));
        return sb.toString();
    }

    static byte[] desdeBase32(String s) {
        String t = s.replace("=", "").replace(" ", "").toUpperCase();
        ByteBuffer out = ByteBuffer.allocate(t.length() * 5 / 8);
        int buffer = 0, bits = 0;
        for (char ch : t.toCharArray()) {
            int v = BASE32.indexOf(ch);
            if (v < 0) throw new IllegalArgumentException("Base32 inválido");
            buffer = (buffer << 5) | v;
            bits += 5;
            if (bits >= 8) {
                out.put((byte) ((buffer >> (bits - 8)) & 0xff));
                bits -= 8;
            }
        }
        return out.array();
    }
}

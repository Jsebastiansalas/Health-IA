package co.medtender.api.privacidad;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.Base64;
import javax.crypto.Cipher;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Lee las preguntas y respuestas que el agente guarda cifradas ({@code agente/app/privacidad/cifrado_columnas.py}):
 * {@code mtd1:} + base64 de vector inicial y texto, AES-256-GCM con {@code DATOS_CLAVE}. La API solo las lee (para
 * «Descargar mis datos»); quien escribe es el agente. Es una clave distinta de {@code CIFRADO_CLAVE}, que protege
 * secretos que el agente no debe poder abrir.
 */
@Component
public class CifradoDatos {

    private static final String PREFIJO = "mtd1:";
    private static final int IV = 12;

    private final SecretKey clave;
    private final ObjectMapper json;

    public CifradoDatos(@Value("${medtender.datos.clave:}") String claveBase64, ObjectMapper json) {
        this.json = json;
        if (claveBase64 == null || claveBase64.isBlank()) {
            this.clave = null;
            return;
        }
        byte[] bytes;
        try {
            bytes = Base64.getDecoder().decode(claveBase64.strip());
        } catch (IllegalArgumentException e) {
            bytes = new byte[0];
        }
        if (bytes.length != 32) {
            throw new IllegalStateException("DATOS_CLAVE debe ser de 32 bytes en base64");
        }
        this.clave = new SecretKeySpec(bytes, "AES");
    }

    /** El texto en claro. Lo que se guardó sin cifrar pasa igual. */
    public String texto(String guardado) {
        if (guardado == null || !guardado.startsWith(PREFIJO)) {
            return guardado;
        }
        if (clave == null) {
            throw new IllegalStateException("Hay datos cifrados y falta DATOS_CLAVE");
        }
        try {
            byte[] todo = Base64.getDecoder().decode(guardado.substring(PREFIJO.length()));
            Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
            c.init(Cipher.DECRYPT_MODE, clave, new GCMParameterSpec(128, todo, 0, IV));
            return new String(c.doFinal(todo, IV, todo.length - IV), StandardCharsets.UTF_8);
        } catch (GeneralSecurityException | IllegalArgumentException e) {
            throw new IllegalStateException("No se pudo descifrar un dato guardado: ¿cambió DATOS_CLAVE?", e);
        }
    }

    /** La respuesta guardada: si viene envuelta en {"cifrado": ...}, la abre. */
    public JsonNode respuesta(JsonNode guardada) {
        JsonNode cifrado = guardada.get("cifrado");
        if (cifrado == null || !cifrado.asText().startsWith(PREFIJO)) {
            return guardada;
        }
        try {
            return json.readTree(texto(cifrado.asText()));
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("La respuesta descifrada no es válida", e);
        }
    }
}

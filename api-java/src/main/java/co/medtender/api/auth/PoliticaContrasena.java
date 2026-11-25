package co.medtender.api.auth;

import co.medtender.api.security.PasswordService;
import co.medtender.api.web.ApiException;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.HexFormat;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

/**
 * Reglas de una contraseña nueva: entre 10 caracteres y 72 bytes, que no sea de las más comunes, que no contenga
 * el correo ni el nombre, y que no aparezca en filtraciones conocidas (Have I Been Pwned por k-anonimato: solo
 * viajan los 5 primeros caracteres del SHA-1; la contraseña nunca sale del servidor). Si ese servicio no
 * responde, no se bloquea el registro (se deja constancia en el log).
 */
@Component
public class PoliticaContrasena {

    private static final Logger log = LoggerFactory.getLogger(PoliticaContrasena.class);
    private static final int MINIMO = 10;
    private static final Set<String> COMUNES = Set.of(
            "1234567890", "12345678910", "0123456789", "contraseña", "contrasena", "contrasena1", "contraseña1",
            "contrasena123", "password", "password1", "password123", "passw0rd123", "qwertyuiop", "qwerty12345",
            "asdfghjkl1", "1q2w3e4r5t", "abc1234567", "abcdefghij", "iloveyou12", "teamo12345", "colombia123",
            "colombia2024", "colombia2025", "colombia2026", "medtender1", "medtender123", "administrador",
            "admin12345", "bienvenido1", "bienvenido123", "1111111111", "0000000000", "aaaaaaaaaa", "micontraseña",
            "micontrasena", "salud12345", "hospital123");

    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
    private final boolean consultarFiltraciones;
    private final String urlFiltraciones;

    public PoliticaContrasena(@Value("${medtender.contrasenas.consultar-filtraciones:true}") boolean consultarFiltraciones,
                              @Value("${medtender.contrasenas.url-filtraciones:https://api.pwnedpasswords.com/range/}") String url) {
        this.consultarFiltraciones = consultarFiltraciones;
        this.urlFiltraciones = url;
    }

    private static ApiException rechazo(String mensaje, String codigo) {
        return new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, mensaje, Map.of("codigo", codigo));
    }

    /** Lanza 422 con un código estable si la contraseña no sirve. */
    public void exigir(String password, String email, String nombre) {
        if (password == null || password.length() < MINIMO) {
            throw rechazo("La contraseña debe tener al menos 10 caracteres", "contrasena_corta");
        }
        if (PasswordService.excedeLimite(password)) {
            throw rechazo("La contraseña no puede superar 72 bytes", "contrasena_larga");
        }
        String p = password.toLowerCase(Locale.ROOT);
        if (COMUNES.contains(p) || p.chars().distinct().count() <= 2) {
            throw rechazo("Esa contraseña es de las más usadas; elige otra", "contrasena_comun");
        }
        String usuarioCorreo = email == null ? "" : email.toLowerCase(Locale.ROOT).split("@")[0];
        if (usuarioCorreo.length() >= 4 && p.contains(usuarioCorreo)) {
            throw rechazo("La contraseña no puede contener tu correo", "contrasena_personal");
        }
        if (nombre != null) {
            for (String parte : nombre.toLowerCase(Locale.ROOT).split("\\s+")) {
                if (parte.length() >= 4 && p.contains(parte)) {
                    throw rechazo("La contraseña no puede contener tu nombre", "contrasena_personal");
                }
            }
        }
        if (consultarFiltraciones && filtrada(password)) {
            throw rechazo("Esa contraseña apareció en filtraciones de datos de otros sitios; elige otra", "contrasena_filtrada");
        }
    }

    boolean filtrada(String password) {
        try {
            String sha1 = HexFormat.of().withUpperCase().formatHex(MessageDigest.getInstance("SHA-1").digest(password.getBytes(StandardCharsets.UTF_8)));
            String prefijo = sha1.substring(0, 5);
            String sufijo = sha1.substring(5);
            HttpRequest req = HttpRequest.newBuilder(java.net.URI.create(urlFiltraciones + prefijo))
                    .timeout(Duration.ofSeconds(3))
                    .header("Add-Padding", "true")
                    .header("User-Agent", "MedTender")
                    .GET().build();
            HttpResponse<String> r = http.send(req, HttpResponse.BodyHandlers.ofString());
            if (r.statusCode() != 200) {
                log.warn("Consulta de contraseñas filtradas respondió {}: no se bloquea", r.statusCode());
                return false;
            }
            for (String linea : r.body().split("\n")) {
                String[] partes = linea.strip().split(":");
                if (partes.length == 2 && partes[0].equalsIgnoreCase(sufijo) && !"0".equals(partes[1].strip())) {
                    return true;
                }
            }
            return false;
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        } catch (Exception e) {
            if (e instanceof InterruptedException) Thread.currentThread().interrupt();
            log.warn("No se pudo consultar contraseñas filtradas ({}): no se bloquea", e.getClass().getSimpleName());
            return false;
        }
    }
}

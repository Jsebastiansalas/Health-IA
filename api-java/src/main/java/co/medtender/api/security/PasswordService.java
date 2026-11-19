package co.medtender.api.security;

import java.nio.charset.StandardCharsets;
import java.util.concurrent.Semaphore;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;

/**
 * bcrypt consume un nucleo entero durante ~250 ms. Un semaforo con tantos permisos como nucleos
 * acota el trabajo simultaneo: el resto espera en cola sin competir por la CPU. Los hashes
 * $2b$ generados por el servicio Python anterior son validos aqui.
 */
@Service
public class PasswordService {

    /** bcrypt solo procesa 72 bytes; se rechaza en vez de truncar en silencio. */
    public static final int MAX_BYTES = 72;

    private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder(12);
    private final Semaphore cupo = new Semaphore(Math.max(2, Runtime.getRuntime().availableProcessors()));

    /** Hash ficticio para igualar el tiempo de respuesta cuando el correo no existe. */
    private final String hashFicticio = encoder.encode("dummy-password-para-timing");

    public static boolean excedeLimite(String password) {
        return password != null && password.getBytes(StandardCharsets.UTF_8).length > MAX_BYTES;
    }

    public String hash(String password) {
        cupo.acquireUninterruptibly();
        try {
            return encoder.encode(password);
        } finally {
            cupo.release();
        }
    }

    public boolean verificar(String password, String hash) {
        cupo.acquireUninterruptibly();
        try {
            return encoder.matches(password, hash == null ? hashFicticio : hash);
        } catch (IllegalArgumentException e) {
            return false;
        } finally {
            cupo.release();
        }
    }
}

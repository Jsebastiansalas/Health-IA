package co.medtender.api.config;

import jakarta.servlet.MultipartConfigElement;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermissions;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.util.unit.DataSize;
import org.springframework.boot.web.servlet.MultipartConfigFactory;

/**
 * Los archivos subidos se guardan SIEMPRE dentro del directorio efimero aislado (no en el
 * temporal del sistema). Asi cualquier resto de una subida interrumpida queda bajo el barrido de
 * archivos huerfanos del agente.
 */
@Configuration
public class MultipartConfig {

    @Bean
    MultipartConfigElement multipartConfigElement(IngestaProperties props) throws IOException {
        Path dir = props.ephemeralDir().toAbsolutePath();
        Files.createDirectories(dir);
        try {
            Files.setPosixFilePermissions(dir, PosixFilePermissions.fromString("rwx------"));
        } catch (UnsupportedOperationException ignorado) {
            // Windows: sin permisos POSIX.
        }
        MultipartConfigFactory f = new MultipartConfigFactory();
        f.setLocation(dir.toString());
        f.setFileSizeThreshold(DataSize.ofBytes(0)); // nada se queda en memoria: todo va a disco
        f.setMaxFileSize(DataSize.ofBytes(props.maxUploadBytes()));
        f.setMaxRequestSize(DataSize.ofBytes(props.maxUploadBytes() + 64 * 1024));
        return f.createMultipartConfig();
    }
}

package co.medtender.api.ingesta;

import co.medtender.api.config.IngestaProperties;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;
import org.springframework.stereotype.Component;

/**
 * Directorio aislado donde vive temporalmente cada PDF mientras se indexa. El nombre del archivo
 * es siempre {documento_id}.pdf: el nombre original del cliente nunca se usa para construir rutas.
 * Java escribe; el agente Python lo lee y lo borra al terminar (o lo borra Java si lo rechaza).
 */
@Component
public class AlmacenEfimero {

    public static final String SUFIJO_PARCIAL = ".part";

    private final Path directorio;

    public AlmacenEfimero(IngestaProperties props) throws IOException {
        this.directorio = props.ephemeralDir().toAbsolutePath();
        Files.createDirectories(directorio);
    }

    public Path directorio() {
        return directorio;
    }

    public Path rutaPdf(UUID documentoId) {
        return directorio.resolve(documentoId + ".pdf");
    }

    public Path rutaParcial(UUID documentoId) {
        return directorio.resolve(documentoId + SUFIJO_PARCIAL);
    }

    /** Equivalente a deleteIfExists. Devuelve true si el archivo existia. */
    public boolean borrar(Path ruta) {
        try {
            return Files.deleteIfExists(ruta);
        } catch (IOException e) {
            throw new java.io.UncheckedIOException("No se pudo borrar " + ruta.getFileName(), e);
        }
    }

    /** Borra el PDF y su version parcial; true si alguno existia. */
    public boolean borrarTodo(UUID documentoId) {
        boolean pdf = borrar(rutaPdf(documentoId));
        boolean parcial = borrar(rutaParcial(documentoId));
        return pdf || parcial;
    }
}

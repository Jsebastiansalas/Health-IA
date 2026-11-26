package co.medtender.api.ingesta;

import co.medtender.api.config.IngestaProperties;
import co.medtender.api.domain.FormatoDocumento;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;
import org.springframework.stereotype.Component;

/**
 * Directorio aislado donde vive temporalmente cada documento (PDF o foto) mientras se indexa. El nombre
 * del archivo es siempre {documento_id}{extension del formato real}: el nombre original del cliente nunca
 * se usa para construir rutas.
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
        return rutaDocumento(documentoId, FormatoDocumento.PDF);
    }

    /** {id}.pdf, {id}.jpg, {id}.png o {id}.heic: el nombre lo decide el formato real, no el cliente. */
    public Path rutaDocumento(UUID documentoId, FormatoDocumento formato) {
        return directorio.resolve(documentoId + formato.extension());
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

    /** Borra el documento (en cualquier formato) y su version parcial; true si alguno existia. */
    public boolean borrarTodo(UUID documentoId) {
        boolean alguno = false;
        for (FormatoDocumento f : FormatoDocumento.values()) {
            alguno |= borrar(rutaDocumento(documentoId, f));
        }
        return borrar(rutaParcial(documentoId)) || alguno;
    }
}

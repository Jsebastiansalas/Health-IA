package co.medtender.api.ingesta;

import java.io.IOException;
import java.nio.file.Path;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.InvalidPasswordException;
import org.apache.tika.Tika;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Validacion del PDF recibido: tipo real por firma binaria (Apache Tika) y estructura (PDFBox).
 * Se rechazan los PDF que piden contrasena para abrirse; los que solo tienen contrasena de
 * propietario (restricciones de impresion o copia, comunes en documentos oficiales) se abren con
 * contrasena vacia y su texto es extraible, asi que se aceptan.
 */
@Component
public class InspectorPdf {

    private static final Logger log = LoggerFactory.getLogger(InspectorPdf.class);

    /** La especificacion permite que la cabecera %PDF- aparezca dentro del primer KB. */
    static final int VENTANA_CABECERA = 1024;

    private final Tika tika = new Tika();

    public static class PdfInvalidoException extends Exception {
        public PdfInvalidoException(String mensaje) {
            super(mensaje);
        }
    }

    /** Instantaneo: no parsea nada. Tika decide el tipo; se tolera basura previa a %PDF- dentro del primer KB. */
    public boolean tieneFirmaPdf(byte[] cabecera) {
        byte[] ventana = Arrays.copyOf(cabecera, Math.min(cabecera.length, VENTANA_CABECERA));
        if ("application/pdf".equals(tika.detect(ventana))) {
            return true;
        }
        String texto = new String(ventana, java.nio.charset.StandardCharsets.ISO_8859_1);
        return texto.contains("%PDF-");
    }

    /** Bloqueante. Devuelve el total de paginas. */
    public int inspeccionar(Path ruta) throws PdfInvalidoException {
        try (PDDocument doc = Loader.loadPDF(new RandomAccessReadBufferedFile(ruta.toFile()))) {
            int total = doc.getNumberOfPages();
            if (total == 0) {
                throw new PdfInvalidoException("El PDF no tiene páginas");
            }
            return total;
        } catch (InvalidPasswordException e) {
            throw new PdfInvalidoException("El PDF está protegido con contraseña");
        } catch (PdfInvalidoException e) {
            throw e;
        } catch (IOException | RuntimeException e) {
            log.info("PDF ilegible: {}", e.toString());
            throw new PdfInvalidoException("PDF corrupto o ilegible");
        }
    }
}

package co.medtender.api.ingesta;

import co.medtender.api.domain.FormatoDocumento;
import java.io.IOException;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Optional;
import javax.imageio.ImageIO;
import javax.imageio.ImageReader;
import javax.imageio.stream.ImageInputStream;
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

    /** Una foto de movil ronda los 12-50 megapixeles; por encima de esto es una bomba de descompresion. */
    static final long MAX_PIXELES = 100_000_000L;

    /**
     * Formato real por la firma binaria (Tika), instantaneo y sin parsear. Vacio si no es un PDF ni una imagen
     * soportada: el tipo que declare el cliente o la extension del nombre no cuentan.
     */
    public Optional<FormatoDocumento> detectarFormato(byte[] cabecera) {
        if (tieneFirmaPdf(cabecera)) {
            return Optional.of(FormatoDocumento.PDF);
        }
        String tipo = tika.detect(Arrays.copyOf(cabecera, Math.min(cabecera.length, VENTANA_CABECERA)));
        return switch (tipo) {
            case "image/jpeg" -> Optional.of(FormatoDocumento.JPG);
            case "image/png" -> Optional.of(FormatoDocumento.PNG);
            case "image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence" ->
                    Optional.of(FormatoDocumento.HEIC);
            default -> Optional.empty();
        };
    }

    /**
     * Una imagen cuenta como una pagina. JPG y PNG se validan leyendo solo las dimensiones (sin decodificar
     * los pixeles) para rechazar archivos corruptos o desproporcionados; HEIC no lo lee ImageIO, asi que lo
     * valida el agente al decodificarlo.
     */
    public int inspeccionarImagen(Path ruta, FormatoDocumento formato) throws PdfInvalidoException {
        if (formato == FormatoDocumento.HEIC) {
            return 1;
        }
        try (ImageInputStream in = ImageIO.createImageInputStream(ruta.toFile())) {
            var lectores = ImageIO.getImageReaders(in);
            if (!lectores.hasNext()) {
                throw new PdfInvalidoException("Imagen corrupta o ilegible");
            }
            ImageReader lector = lectores.next();
            try {
                lector.setInput(in);
                long pixeles = (long) lector.getWidth(0) * lector.getHeight(0);
                if (pixeles <= 0 || pixeles > MAX_PIXELES) {
                    throw new PdfInvalidoException("La imagen es demasiado grande (más de 100 megapíxeles)");
                }
                return 1;
            } finally {
                lector.dispose();
            }
        } catch (PdfInvalidoException e) {
            throw e;
        } catch (IOException | RuntimeException e) {
            log.info("Imagen ilegible: {}", e.toString());
            throw new PdfInvalidoException("Imagen corrupta o ilegible");
        }
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

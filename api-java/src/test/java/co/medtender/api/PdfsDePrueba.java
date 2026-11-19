package co.medtender.api;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.pdmodel.encryption.StandardProtectionPolicy;

/** PDFs generados al vuelo. Cada uno es distinto (titulo unico) para no chocar con la deteccion de duplicados. */
public final class PdfsDePrueba {

    private PdfsDePrueba() {}

    public static byte[] valido(int paginas) {
        return generar(paginas, null, null);
    }

    /** Pide contrasena para abrirse: debe rechazarse. */
    public static byte[] conClaveDeUsuario() {
        return generar(1, "dueno-secreto", "clave-usuario");
    }

    /** Solo contrasena de propietario (restricciones de copia): se abre con clave vacia y se acepta. */
    public static byte[] soloClaveDePropietario() {
        return generar(1, "dueno-secreto", "");
    }

    /** Cabecera correcta pero cuerpo roto. */
    public static byte[] corrupto() {
        return ("%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 99 0 R >> endobj\n" + UUID.randomUUID()
                + "\nesto no es un pdf valido ni tiene xref\n").getBytes(StandardCharsets.ISO_8859_1);
    }

    public static byte[] noEsPdf() {
        return ("Hola, esto es un archivo de texto " + UUID.randomUUID()).getBytes(StandardCharsets.UTF_8);
    }

    /** PDF valido con la cadena de prueba EICAR anexada despues del %%EOF. */
    public static byte[] conEicar() {
        byte[] base = valido(1);
        byte[] eicar = ("\n" + Infra.EICAR + "\n").getBytes(StandardCharsets.ISO_8859_1);
        byte[] r = new byte[base.length + eicar.length];
        System.arraycopy(base, 0, r, 0, base.length);
        System.arraycopy(eicar, 0, r, base.length, eicar.length);
        return r;
    }

    private static byte[] generar(int paginas, String propietario, String usuario) {
        try (PDDocument doc = new PDDocument()) {
            for (int i = 0; i < paginas; i++) {
                doc.addPage(new PDPage());
            }
            doc.getDocumentInformation().setTitle(UUID.randomUUID().toString());
            if (propietario != null) {
                var politica = new StandardProtectionPolicy(propietario, usuario, new AccessPermission());
                politica.setEncryptionKeyLength(128);
                doc.protect(politica);
            }
            ByteArrayOutputStream salida = new ByteArrayOutputStream();
            doc.save(salida);
            return salida.toByteArray();
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }
}

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

    // ---------- imagenes ----------

    private static byte[] imagen(String formato, int ancho, int alto) {
        try {
            var img = new java.awt.image.BufferedImage(ancho, alto, java.awt.image.BufferedImage.TYPE_INT_RGB);
            var g = img.createGraphics();
            g.setColor(java.awt.Color.WHITE);
            g.fillRect(0, 0, ancho, alto);
            g.setColor(java.awt.Color.BLACK);
            // Distinta cada vez: el contenido cambia el SHA-256 y evita la deteccion de duplicados.
            g.drawString("Resultado " + UUID.randomUUID(), 10, alto / 2);
            g.dispose();
            var salida = new ByteArrayOutputStream();
            javax.imageio.ImageIO.write(img, formato, salida);
            return salida.toByteArray();
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    public static byte[] png() {
        return imagen("png", 320, 200);
    }

    public static byte[] jpg() {
        return imagen("jpg", 320, 200);
    }

    /** Firma PNG verdadera seguida de basura: Tika la detecta como PNG pero no se puede leer. */
    public static byte[] pngCorrupto() {
        byte[] firma = {(byte) 0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A};
        byte[] basura = ("no-es-una-imagen-" + UUID.randomUUID()).repeat(20).getBytes(StandardCharsets.UTF_8);
        var salida = new ByteArrayOutputStream();
        salida.writeBytes(firma);
        salida.writeBytes(basura);
        return salida.toByteArray();
    }

    /** Un GIF: es una imagen, pero no un formato soportado. */
    public static byte[] gif() {
        return imagen("gif", 40, 40);
    }

    /** Cabecera ISO-BMFF de un HEIC (caja ftyp con la marca heic). Basta para que se reconozca el formato. */
    public static byte[] cabeceraHeic() {
        byte[] ftyp = {0, 0, 0, 0x18, 'f', 't', 'y', 'p', 'h', 'e', 'i', 'c', 0, 0, 0, 0, 'm', 'i', 'f', '1', 'h', 'e', 'i', 'c'};
        var salida = new ByteArrayOutputStream();
        salida.writeBytes(ftyp);
        salida.writeBytes(("relleno-" + UUID.randomUUID()).getBytes(StandardCharsets.UTF_8));
        return salida.toByteArray();
    }
}

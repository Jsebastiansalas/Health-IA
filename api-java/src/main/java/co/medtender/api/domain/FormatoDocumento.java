package co.medtender.api.domain;

/**
 * Formato real del archivo recibido (decidido por su contenido, nunca por la extension o el tipo que declare
 * el cliente). Cada formato lleva su extension en el directorio efimero: {id}.pdf, {id}.jpg...
 */
public enum FormatoDocumento {
    PDF(".pdf"),
    JPG(".jpg"),
    PNG(".png"),
    HEIC(".heic");

    private final String extension;

    FormatoDocumento(String extension) {
        this.extension = extension;
    }

    public String extension() {
        return extension;
    }

    public boolean esImagen() {
        return this != PDF;
    }
}

package co.medtender.api.privacidad;

/** Salida de correo. Se puede sustituir (pruebas, otro proveedor) definiendo otro bean. */
public interface CorreoEnvio {

    void enviar(String para, String asunto, String cuerpo);

    /** Falso si el servidor no tiene por dónde enviar: lo que solo funciona con el correo debe decirlo. */
    default boolean disponible() {
        return true;
    }
}

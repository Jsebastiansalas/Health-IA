package co.medtender.api.push;

/** Envio de una notificacion SIN contenido a un dispositivo. Se puede sustituir en las pruebas. */
public interface PushEnvio {

    enum Resultado {
        ENVIADO,
        /** El servicio dice que la suscripcion ya no existe: hay que borrarla. */
        CADUCADA,
        FALLO
    }

    Resultado enviar(String endpoint);
}

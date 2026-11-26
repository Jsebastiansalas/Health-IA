package co.medtender.api.limites;

/** Contadores de ventana fija. Cada clave nace con expiracion: un contador nunca queda eterno. */
public interface AlmacenLimites {

    /** Suma 1 a la clave y devuelve la cuenta y los segundos que faltan para que expire. */
    Conteo golpear(String clave, int ventanaS);

    /** Cuenta actual sin modificar. */
    Conteo contar(String clave);

    void reiniciar();

    record Conteo(long cuenta, int restanteS) {}
}

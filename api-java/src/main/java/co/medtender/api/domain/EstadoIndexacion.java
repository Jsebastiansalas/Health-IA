package co.medtender.api.domain;

import java.util.EnumMap;
import java.util.Map;
import java.util.Set;

/**
 * Estados del pipeline, compartidos por BD y UI.
 * RECIBIDO -> VALIDANDO -> EN_COLA -> EXTRAYENDO_OCR -> FRAGMENTANDO -> VECTORIZANDO
 *          -> INDEXADO_PENDIENTE_PURGA (solo politica DIFERIDO_1H) -> INDEXADO_Y_PURGADO.
 * Cualquier estado no final puede pasar a ERROR_PURGADO. Java gobierna hasta EN_COLA; el agente
 * Python escribe el resto.
 */
public enum EstadoIndexacion {
    RECIBIDO(5),
    VALIDANDO(10),
    EN_COLA(15),
    EXTRAYENDO_OCR(35),
    FRAGMENTANDO(60),
    VECTORIZANDO(80),
    INDEXADO_PENDIENTE_PURGA(100),
    INDEXADO_Y_PURGADO(100),
    ERROR_PURGADO(100);

    private static final Map<EstadoIndexacion, Set<EstadoIndexacion>> TRANSICIONES = new EnumMap<>(EstadoIndexacion.class);

    static {
        TRANSICIONES.put(RECIBIDO, Set.of(VALIDANDO));
        TRANSICIONES.put(VALIDANDO, Set.of(EN_COLA));
        TRANSICIONES.put(EN_COLA, Set.of(EXTRAYENDO_OCR));
        TRANSICIONES.put(EXTRAYENDO_OCR, Set.of(FRAGMENTANDO, EN_COLA));
        TRANSICIONES.put(FRAGMENTANDO, Set.of(VECTORIZANDO, EN_COLA));
        TRANSICIONES.put(VECTORIZANDO, Set.of(INDEXADO_PENDIENTE_PURGA, INDEXADO_Y_PURGADO));
        TRANSICIONES.put(INDEXADO_PENDIENTE_PURGA, Set.of(INDEXADO_Y_PURGADO));
        TRANSICIONES.put(INDEXADO_Y_PURGADO, Set.of());
        TRANSICIONES.put(ERROR_PURGADO, Set.of());
    }

    private final int progreso;

    EstadoIndexacion(int progreso) {
        this.progreso = progreso;
    }

    public int progreso() {
        return progreso;
    }

    public boolean esFinal() {
        return this == INDEXADO_Y_PURGADO || this == ERROR_PURGADO;
    }

    public boolean puedePasarA(EstadoIndexacion nuevo) {
        if (nuevo == ERROR_PURGADO) {
            return !esFinal();
        }
        return TRANSICIONES.get(this).contains(nuevo);
    }
}

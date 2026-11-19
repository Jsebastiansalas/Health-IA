package co.medtender.api.limites;

import java.util.concurrent.ConcurrentHashMap;

/** Version en memoria: solo para pruebas o ejecucion con un unico proceso. */
public class AlmacenMemoria implements AlmacenLimites {

    private record Entrada(long cuenta, long expiraNs) {}

    private final ConcurrentHashMap<String, Entrada> datos = new ConcurrentHashMap<>();

    @Override
    public Conteo golpear(String clave, int ventanaS) {
        long ahora = System.nanoTime();
        Entrada e = datos.compute(clave, (k, previa) -> {
            if (previa == null || previa.expiraNs() <= ahora) {
                return new Entrada(1, ahora + ventanaS * 1_000_000_000L);
            }
            return new Entrada(previa.cuenta() + 1, previa.expiraNs());
        });
        return new Conteo(e.cuenta(), restante(e, ahora));
    }

    @Override
    public Conteo contar(String clave) {
        long ahora = System.nanoTime();
        Entrada e = datos.get(clave);
        if (e == null || e.expiraNs() <= ahora) {
            return new Conteo(0, 0);
        }
        return new Conteo(e.cuenta(), restante(e, ahora));
    }

    private static int restante(Entrada e, long ahora) {
        return (int) Math.max(1, (e.expiraNs() - ahora) / 1_000_000_000L);
    }

    @Override
    public void reiniciar() {
        datos.clear();
    }
}

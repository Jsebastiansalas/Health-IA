package co.medtender.api.limites;

import co.medtender.api.config.MedtenderProperties;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * Limites de peticiones (ventana fija). Si el almacen falla se permite la solicitud (fail-open) y se
 * deja constancia: es preferible no tumbar el servicio por el limitador, y el resto de defensas
 * (bcrypt, permisos) siguen activas.
 */
@Service
public class Limitador {

    private static final Logger log = LoggerFactory.getLogger(Limitador.class);

    public record Resultado(boolean permitido, long cuenta, int reintentarEnS) {}

    private static final Resultado LIBRE = new Resultado(true, 0, 0);

    private final AlmacenLimites almacen;
    private final MedtenderProperties props;
    private final MeterRegistry metricas;

    public Limitador(AlmacenLimites almacen, MedtenderProperties props, MeterRegistry metricas) {
        this.almacen = almacen;
        this.props = props;
        this.metricas = metricas;
    }

    private static String clave(String regla, String identidad, int ventanaS) {
        return "rl:" + regla + ":" + ventanaS + ":" + identidad;
    }

    /** Registra una solicitud y dice si cabe dentro del limite. */
    public Resultado golpear(String regla, String identidad, int limite, int ventanaS) {
        if (!props.rateLimit().habilitado()) {
            return LIBRE;
        }
        try {
            var c = almacen.golpear(clave(regla, identidad, ventanaS), ventanaS);
            return new Resultado(c.cuenta() <= limite, c.cuenta(), c.restanteS());
        } catch (RuntimeException e) {
            metricas.counter("medtender_limite_fallos_total").increment();
            log.warn("Almacen de limites no disponible; se permite la solicitud", e);
            return LIBRE;
        }
    }

    /** Ya se alcanzo el limite? No suma. Sirve para bloquear tras N fallos. */
    public Resultado excedido(String regla, String identidad, int limite, int ventanaS) {
        if (!props.rateLimit().habilitado()) {
            return LIBRE;
        }
        try {
            var c = almacen.contar(clave(regla, identidad, ventanaS));
            return new Resultado(c.cuenta() < limite, c.cuenta(), c.restanteS());
        } catch (RuntimeException e) {
            metricas.counter("medtender_limite_fallos_total").increment();
            return LIBRE;
        }
    }

    public LimiteExcedidoException rechazar(String regla, int reintentarEnS) {
        metricas.counter("medtender_limite_rechazos_total", "regla", regla).increment();
        log.warn("Limite excedido regla={}", regla);
        return new LimiteExcedidoException(reintentarEnS);
    }

    public void exigir(String regla, String identidad, int limite, int ventanaS) {
        Resultado r = golpear(regla, identidad, limite, ventanaS);
        if (!r.permitido()) {
            throw rechazar(regla, r.reintentarEnS());
        }
    }
}

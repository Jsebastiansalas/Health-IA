package co.medtender.api.config;

import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

/** Arranque seguro: en produccion una configuracion peligrosa impide iniciar el servicio. */
@Component
public class ValidadorConfiguracion {

    private static final Logger log = LoggerFactory.getLogger(ValidadorConfiguracion.class);
    private final MedtenderProperties props;

    public ValidadorConfiguracion(MedtenderProperties props) {
        this.props = props;
        validar(); // antes de aceptar trafico
    }

    private void validar() {
        List<List<String>> p = props.problemas();
        List<String> fatales = p.get(0);
        List<String> avisos = p.get(1);
        avisos.forEach(a -> log.warn("Configuracion: {}", a));
        if (props.esProduccion() && !fatales.isEmpty()) {
            throw new IllegalStateException("Configuracion insegura para produccion: " + String.join("; ", fatales));
        }
        fatales.forEach(f -> log.warn("Configuracion (fatal en produccion): {}", f));
    }

    @EventListener(ApplicationReadyEvent.class)
    void listo() {
        log.info("API lista (entorno={})", props.entorno());
    }
}

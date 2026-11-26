package co.medtender.api.ingesta;

import co.medtender.api.config.IngestaProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class AntivirusConfig {

    private static final Logger log = LoggerFactory.getLogger(AntivirusConfig.class);

    @Bean
    VirusScanner virusScanner(IngestaProperties props) {
        var av = props.antivirus();
        if ("noop".equals(av.backend())) {
            // Solo desarrollo: nunca en produccion.
            return ruta -> {
                log.warn("Antivirus deshabilitado (ANTIVIRUS_BACKEND=noop): {} sin escanear", ruta.getFileName());
                return VirusScanner.ResultadoEscaneo.ok();
            };
        }
        return new ClamavScanner(av.host(), av.port(), av.timeoutS());
    }
}

package co.medtender.api.ingesta;

import co.medtender.api.config.IngestaProperties;
import java.time.Duration;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

/**
 * Cliente del agente de IA (FastAPI, red interna). Solo se le habla con el token compartido
 * {@code X-Internal-Token}; el agente no autentica usuarios, confia en lo que Java ya autorizo.
 */
@Component
public class AgenteClient {

    private static final Logger log = LoggerFactory.getLogger(AgenteClient.class);

    public static class AgenteNoDisponibleException extends Exception {
        public AgenteNoDisponibleException(String mensaje, Throwable causa) {
            super(mensaje, causa);
        }
    }

    private final RestClient http;
    private final IngestaProperties.Agente cfg;
    private final long retrocesoMs;

    public AgenteClient(IngestaProperties props, org.springframework.core.env.Environment env) {
        this.cfg = props.agente();
        this.retrocesoMs = env.getProperty("medtender.ingesta.agente.retroceso-ms", Long.class, 500L);
        var fabrica = new SimpleClientHttpRequestFactory();
        fabrica.setConnectTimeout(Duration.ofSeconds(cfg.timeoutS()));
        fabrica.setReadTimeout(Duration.ofSeconds(cfg.timeoutS()));
        this.http = RestClient.builder().baseUrl(cfg.url()).requestFactory(fabrica).build();
    }

    /**
     * Pide al agente que procese el documento (extraccion, OCR, fragmentos, embeddings y purga).
     * Reintenta ante errores de red y 5xx; un 4xx (p. ej. token invalido) no se reintenta.
     */
    public void encolarProcesamiento(UUID documentoId) throws AgenteNoDisponibleException {
        Exception ultimo = null;
        for (int intento = 1; intento <= Math.max(1, cfg.reintentos()); intento++) {
            try {
                http.post().uri("/internal/v1/documentos/{id}/procesar", documentoId)
                        .header("X-Internal-Token", cfg.token() == null ? "" : cfg.token())
                        .header("X-Request-ID", MDC.get("request_id") == null ? "" : MDC.get("request_id"))
                        .body(Map.of())
                        .retrieve()
                        .toBodilessEntity();
                log.info("Documento {} entregado al agente", documentoId);
                return;
            } catch (RestClientResponseException e) {
                HttpStatusCode codigo = e.getStatusCode();
                ultimo = e;
                if (codigo.is4xxClientError()) {
                    throw new AgenteNoDisponibleException("El agente rechazo la solicitud (" + codigo.value() + ")", e);
                }
            } catch (RuntimeException e) {
                ultimo = e;
            }
            log.warn("Agente no disponible (intento {}/{}): {}", intento, cfg.reintentos(), ultimo.toString());
            if (intento < cfg.reintentos()) {
                try {
                    Thread.sleep(retrocesoMs * (1L << (intento - 1)));
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        throw new AgenteNoDisponibleException("El agente no respondio", ultimo);
    }
}

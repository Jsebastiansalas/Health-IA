package co.medtender.api.ingesta;

import co.medtender.api.config.IngestaProperties;
import co.medtender.api.web.ApiException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Duration;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.util.UriComponentsBuilder;

/**
 * Cliente del agente de IA (FastAPI, red interna). Solo se le habla con el token compartido
 * {@code X-Internal-Token}; el agente no autentica usuarios, confia en lo que Java ya autorizo
 * (tenant, expediente y usuario viajan en cada solicitud).
 */
@Component
public class AgenteClient {

    private static final Logger log = LoggerFactory.getLogger(AgenteClient.class);
    static final String MENSAJE_IA_NO_DISPONIBLE = "El servicio de IA no está disponible en este momento; intente de nuevo.";

    public static class AgenteNoDisponibleException extends Exception {
        public AgenteNoDisponibleException(String mensaje, Throwable causa) {
            super(mensaje, causa);
        }
    }

    private final RestClient corto;
    private final RestClient largo;
    private final IngestaProperties.Agente cfg;
    private final ObjectMapper json;
    private final long retrocesoMs;

    public AgenteClient(IngestaProperties props, org.springframework.core.env.Environment env, ObjectMapper json) {
        this.cfg = props.agente();
        this.json = json;
        this.retrocesoMs = env.getProperty("medtender.ingesta.agente.retroceso-ms", Long.class, 500L);
        this.corto = construir(cfg.timeoutS());
        this.largo = construir(cfg.timeoutConsultaS());
    }

    private RestClient construir(int timeoutS) {
        var fabrica = new SimpleClientHttpRequestFactory();
        fabrica.setConnectTimeout(Duration.ofSeconds(cfg.timeoutS()));
        fabrica.setReadTimeout(Duration.ofSeconds(timeoutS));
        return RestClient.builder().baseUrl(cfg.url()).requestFactory(fabrica).build();
    }

    private static String idPeticion() {
        String id = MDC.get("request_id");
        return id == null ? "" : id;
    }

    // ---------- procesamiento de documentos ----------

    /**
     * Pide al agente que procese el documento (extraccion, OCR, fragmentos, embeddings y purga).
     * Reintenta ante errores de red y 5xx; un 4xx (p. ej. token invalido) no se reintenta.
     */
    public void encolarProcesamiento(UUID documentoId) throws AgenteNoDisponibleException {
        Exception ultimo = null;
        for (int intento = 1; intento <= Math.max(1, cfg.reintentos()); intento++) {
            try {
                corto.post().uri("/internal/v1/documentos/{id}/procesar", documentoId)
                        .header("X-Internal-Token", token())
                        .header("X-Request-ID", idPeticion())
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

    // ---------- consultas, modelos y reindexacion (proxy autorizado) ----------

    /** POST JSON al agente. Los errores del agente se traducen a {@link ApiException} sin filtrar detalles internos. */
    public JsonNode post(String ruta, Object cuerpo, boolean espera) {
        return ejecutar(() -> (espera ? largo : corto).post().uri(ruta)
                .header("X-Internal-Token", token())
                .header("X-Request-ID", idPeticion())
                .body(cuerpo)
                .retrieve()
                .body(JsonNode.class));
    }

    public JsonNode get(String ruta, Map<String, ?> parametros) {
        String uri = UriComponentsBuilder.fromPath(ruta)
                .queryParams(multi(parametros)).build().toUriString();
        return ejecutar(() -> corto.get().uri(uri)
                .header("X-Internal-Token", token())
                .header("X-Request-ID", idPeticion())
                .retrieve()
                .body(JsonNode.class));
    }

    private static org.springframework.util.MultiValueMap<String, String> multi(Map<String, ?> m) {
        var r = new org.springframework.util.LinkedMultiValueMap<String, String>();
        m.forEach((k, v) -> r.add(k, String.valueOf(v)));
        return r;
    }

    private JsonNode ejecutar(java.util.function.Supplier<JsonNode> llamada) {
        try {
            return llamada.get();
        } catch (RestClientResponseException e) {
            throw traducir(e);
        } catch (ResourceAccessException e) {
            log.error("El agente no responde: {}", e.getMessage());
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, MENSAJE_IA_NO_DISPONIBLE);
        }
    }

    /**
     * 404/409/422 del agente son errores de negocio y se reenvian tal cual (su texto es nuestro).
     * Todo lo demas (5xx, token interno rechazado...) es un problema interno: el usuario solo ve un
     * 503 generico y el detalle queda en el log.
     */
    private ApiException traducir(RestClientResponseException e) {
        int codigo = e.getStatusCode().value();
        if (codigo == 404 || codigo == 409 || codigo == 422) {
            return new ApiException(HttpStatus.valueOf(codigo), detalleDe(e));
        }
        log.error("El agente respondio {}: {}", codigo, e.getResponseBodyAsString());
        return new ApiException(HttpStatus.SERVICE_UNAVAILABLE, MENSAJE_IA_NO_DISPONIBLE);
    }

    private String detalleDe(RestClientResponseException e) {
        try {
            JsonNode d = json.readTree(e.getResponseBodyAsString()).get("detail");
            return d != null && d.isTextual() ? d.asText() : "Solicitud inválida";
        } catch (Exception ex) {
            return "Solicitud inválida";
        }
    }

    private String token() {
        return cfg.token() == null ? "" : cfg.token();
    }
}

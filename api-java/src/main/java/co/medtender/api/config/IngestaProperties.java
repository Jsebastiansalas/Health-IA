package co.medtender.api.config;

import java.nio.file.Path;
import org.springframework.boot.context.properties.ConfigurationProperties;

/** Ajustes de la ingesta efimera de PDFs y de la conexion con el agente Python. */
@ConfigurationProperties(prefix = "medtender.ingesta")
public record IngestaProperties(
        Path ephemeralDir,
        int maxUploadMb,
        String embeddingModelDefault,
        String ocrVersionActual,
        Antivirus antivirus,
        Agente agente) {

    public record Antivirus(String backend, String host, int port, int timeoutS) {}

    /** Servicio interno de IA (FastAPI). Solo se le habla por la red interna con un token compartido. */
    public record Agente(String url, String token, int timeoutS, int timeoutConsultaS, int reintentos) {}

    public long maxUploadBytes() {
        return maxUploadMb * 1024L * 1024L;
    }

    /** Dimension del vector que produce el modelo (bge-m3 es de 1024 y se rellena a 1536 al guardar). */
    public static int dimensionDe(String modelo) {
        return modelo != null && modelo.startsWith("bge-m3") ? 1024 : 1536;
    }
}

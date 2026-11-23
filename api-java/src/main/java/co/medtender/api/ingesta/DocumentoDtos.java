package co.medtender.api.ingesta;

import co.medtender.api.domain.ActaPurga;
import co.medtender.api.domain.Documento;
import co.medtender.api.domain.EstadoIndexacion;
import co.medtender.api.domain.MotivoPurga;
import co.medtender.api.domain.TipoDocumento;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

public final class DocumentoDtos {

    private DocumentoDtos() {}

    public record ActaPurgaOut(UUID id, MotivoPurga motivo, String sha256Original, Integer chunksEsperados,
                               Integer chunksVerificados, boolean archivoExistia, String detalle, Instant purgedAt) {
        static ActaPurgaOut de(ActaPurga a) {
            return new ActaPurgaOut(a.getId(), a.getMotivo(), a.getSha256Original(), a.getChunksEsperados(),
                    a.getChunksVerificados(), a.isArchivoExistia(), a.getDetalle(), a.getPurgedAt());
        }
    }

    /** Estado del documento en el pipeline (alimenta la barra de progreso de la UI). */
    public record DocumentoOut(UUID id, UUID expedienteId, String nombreArchivoOriginal, TipoDocumento tipoDocumento,
                               Integer numeroAdenda, String sha256Original, long tamanoBytes, Integer totalPaginas,
                               EstadoIndexacion estadoIndexacion, String motivoError, String embeddingModel,
                               String ocrVersion, String extractorVersion, Integer totalChunksEsperados,
                               Integer totalChunksGuardados, boolean tempFilePurged, Instant uploadedAt,
                               Instant estadoActualizadoAt, Instant purgaProgramadaAt, Instant purgedAt,
                               int paginasOcr, int progreso, boolean avisoOcrDesactualizado, String formato) {

        public static DocumentoOut de(Documento d, String ocrVersionActual) {
            int progreso = d.getEstadoIndexacion().progreso();
            Integer esperados = d.getTotalChunksEsperados();
            if (d.getEstadoIndexacion() == EstadoIndexacion.VECTORIZANDO && esperados != null && esperados > 0) {
                // 80 % -> 99 % segun los fragmentos ya vectorizados.
                int guardados = d.getTotalChunksGuardados() == null ? 0 : d.getTotalChunksGuardados();
                progreso += (int) (19L * guardados / esperados);
            }
            // El OCR cambio de version: conviene volver a cargar el PDF desde el PC (HU4.5).
            boolean aviso = d.getPaginasOcr() > 0 && !d.getOcrVersion().equals(ocrVersionActual);
            return new DocumentoOut(d.getId(), d.getExpedienteId(), d.getNombreArchivoOriginal(), d.getTipoDocumento(),
                    d.getNumeroAdenda(), d.getSha256Original(), d.getTamanoBytes(), d.getTotalPaginas(),
                    d.getEstadoIndexacion(), d.getMotivoError(), d.getEmbeddingModel(), d.getOcrVersion(),
                    d.getExtractorVersion(), esperados, d.getTotalChunksGuardados(), d.isTempFilePurged(),
                    d.getUploadedAt(), d.getEstadoActualizadoAt(), d.getPurgaProgramadaAt(), d.getPurgedAt(),
                    d.getPaginasOcr(), progreso, aviso, d.getFormato().name());
        }
    }

    public record DocumentoDetalleOut(@com.fasterxml.jackson.annotation.JsonUnwrapped DocumentoOut base, List<ActaPurgaOut> actasPurga) {}
}

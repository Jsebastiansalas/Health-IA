package co.medtender.api.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;
import org.hibernate.annotations.DynamicUpdate;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/**
 * Documento en ingesta. Java lo crea y lo gobierna hasta EN_COLA; despues lo actualiza el agente
 * Python. DynamicUpdate evita que Java sobrescriba columnas que Python modifico.
 */
@Entity
@DynamicUpdate
@Table(name = "documentos")
public class Documento {

    @Id
    private UUID id; // lo asigna la aplicacion: el nombre del archivo temporal usa este mismo id

    @Column(name = "tenant_id", nullable = false, updatable = false)
    private UUID tenantId;

    @Column(name = "expediente_id", nullable = false, updatable = false)
    private UUID expedienteId;

    @Column(name = "nombre_archivo_original", nullable = false)
    private String nombreArchivoOriginal;

    @Enumerated(EnumType.STRING)
    @Column(name = "tipo_documento", nullable = false, length = 50)
    private TipoDocumento tipoDocumento;

    @Column(name = "numero_adenda")
    private Integer numeroAdenda = 0;

    @JdbcTypeCode(SqlTypes.CHAR)
    @Column(name = "sha256_original", nullable = false, columnDefinition = "char(64)", length = 64)
    private String sha256Original;

    @Column(name = "tamano_bytes", nullable = false)
    private long tamanoBytes;

    @Column(name = "total_paginas")
    private Integer totalPaginas;

    @Enumerated(EnumType.STRING)
    @Column(name = "estado_indexacion", nullable = false, length = 40)
    private EstadoIndexacion estadoIndexacion;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 10)
    private FormatoDocumento formato = FormatoDocumento.PDF;

    @Column(name = "ocr_version", nullable = false, length = 30)
    private String ocrVersion = "tesseract-5.x-v1";

    @Column(name = "extractor_version", nullable = false, length = 30)
    private String extractorVersion = "pdfium-pdfplumber-v1";

    @Column(name = "embedding_model", nullable = false, length = 80)
    private String embeddingModel;

    @Column(name = "total_chunks_esperados")
    private Integer totalChunksEsperados = 0;

    @Column(name = "total_chunks_guardados")
    private Integer totalChunksGuardados = 0;

    @Column(name = "temp_file_purged", nullable = false)
    private boolean tempFilePurged = false;

    @Column(name = "uploaded_at", nullable = false, updatable = false)
    private Instant uploadedAt = Instant.now();

    @Column(name = "purged_at")
    private Instant purgedAt;

    @Column(name = "motivo_error", columnDefinition = "text")
    private String motivoError;

    @Column(name = "paginas_ocr", nullable = false)
    private int paginasOcr = 0;

    @Column(name = "purga_programada_at")
    private Instant purgaProgramadaAt;

    @Column(name = "estado_actualizado_at", nullable = false)
    private Instant estadoActualizadoAt = Instant.now();

    protected Documento() {}

    public Documento(UUID id, UUID tenantId, UUID expedienteId, String nombre, TipoDocumento tipo, int adenda,
                     String sha256, long tamano, String embeddingModel) {
        this.id = id;
        this.tenantId = tenantId;
        this.expedienteId = expedienteId;
        this.nombreArchivoOriginal = nombre;
        this.tipoDocumento = tipo;
        this.numeroAdenda = adenda;
        this.sha256Original = sha256;
        this.tamanoBytes = tamano;
        this.embeddingModel = embeddingModel;
        this.estadoIndexacion = EstadoIndexacion.RECIBIDO;
    }

    /** Aplica la maquina de estados; una transicion no permitida es un error de programacion. */
    public void transicionar(EstadoIndexacion nuevo) {
        if (!estadoIndexacion.puedePasarA(nuevo)) {
            throw new IllegalStateException(estadoIndexacion + " -> " + nuevo + " no permitido");
        }
        this.estadoIndexacion = nuevo;
        this.estadoActualizadoAt = Instant.now();
    }

    public void marcarPurgado(String motivoError) {
        this.tempFilePurged = true;
        this.purgedAt = Instant.now();
        this.purgaProgramadaAt = null;
        this.motivoError = motivoError;
        this.totalChunksGuardados = 0;
    }

    public UUID getId() { return id; }
    public UUID getTenantId() { return tenantId; }
    public UUID getExpedienteId() { return expedienteId; }
    public String getNombreArchivoOriginal() { return nombreArchivoOriginal; }
    public TipoDocumento getTipoDocumento() { return tipoDocumento; }
    public Integer getNumeroAdenda() { return numeroAdenda; }
    public String getSha256Original() { return sha256Original; }
    public long getTamanoBytes() { return tamanoBytes; }
    public Integer getTotalPaginas() { return totalPaginas; }
    public void setTotalPaginas(Integer p) { this.totalPaginas = p; }
    public EstadoIndexacion getEstadoIndexacion() { return estadoIndexacion; }
    public String getOcrVersion() { return ocrVersion; }
    public String getExtractorVersion() { return extractorVersion; }
    public String getEmbeddingModel() { return embeddingModel; }
    public Integer getTotalChunksEsperados() { return totalChunksEsperados; }
    public Integer getTotalChunksGuardados() { return totalChunksGuardados; }
    public boolean isTempFilePurged() { return tempFilePurged; }
    public Instant getUploadedAt() { return uploadedAt; }
    public Instant getPurgedAt() { return purgedAt; }
    public String getMotivoError() { return motivoError; }
    public int getPaginasOcr() { return paginasOcr; }
    public Instant getPurgaProgramadaAt() { return purgaProgramadaAt; }
    public Instant getEstadoActualizadoAt() { return estadoActualizadoAt; }

    public FormatoDocumento getFormato() { return formato; }

    public void setFormato(FormatoDocumento formato) { this.formato = formato; }
}

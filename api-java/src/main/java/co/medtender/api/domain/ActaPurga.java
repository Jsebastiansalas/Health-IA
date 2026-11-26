package co.medtender.api.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/** Registro auditable de cada borrado de un PDF temporal. */
@Entity
@Table(name = "actas_purga")
public class ActaPurga {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "tenant_id") private UUID tenantId;
    @Column(name = "documento_id") private UUID documentoId;

    @JdbcTypeCode(SqlTypes.CHAR)
    @Column(name = "sha256_original", columnDefinition = "char(64)", length = 64)
    private String sha256Original;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private MotivoPurga motivo;

    @Column(name = "chunks_esperados") private Integer chunksEsperados;
    @Column(name = "chunks_verificados") private Integer chunksVerificados;
    @Column(name = "archivo_existia", nullable = false) private boolean archivoExistia;
    @Column(columnDefinition = "text") private String detalle;
    @Column(name = "purged_at", nullable = false, updatable = false) private Instant purgedAt = Instant.now();

    protected ActaPurga() {}

    public ActaPurga(UUID tenantId, UUID documentoId, String sha256, MotivoPurga motivo, Integer esperados,
                     Integer verificados, boolean archivoExistia, String detalle) {
        this.tenantId = tenantId;
        this.documentoId = documentoId;
        this.sha256Original = sha256;
        this.motivo = motivo;
        this.chunksEsperados = esperados;
        this.chunksVerificados = verificados;
        this.archivoExistia = archivoExistia;
        this.detalle = detalle;
    }

    public UUID getId() { return id; }
    public UUID getTenantId() { return tenantId; }
    public UUID getDocumentoId() { return documentoId; }
    public String getSha256Original() { return sha256Original; }
    public MotivoPurga getMotivo() { return motivo; }
    public Integer getChunksEsperados() { return chunksEsperados; }
    public Integer getChunksVerificados() { return chunksVerificados; }
    public boolean isArchivoExistia() { return archivoExistia; }
    public String getDetalle() { return detalle; }
    public Instant getPurgedAt() { return purgedAt; }
}

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
import org.hibernate.annotations.DynamicUpdate;

@Entity
@DynamicUpdate
@Table(name = "expedientes")
public class Expediente {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "tenant_id", nullable = false, updatable = false)
    private UUID tenantId;

    @Column(name = "codigo_expediente", nullable = false, length = 80)
    private String codigoExpediente;

    @Column(nullable = false, length = 250)
    private String titulo;

    @Column(name = "entidad_contratante", length = 200)
    private String entidadContratante;

    @Enumerated(EnumType.STRING)
    @Column(name = "tipo_expediente", nullable = false, length = 50)
    private TipoExpediente tipoExpediente;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 40)
    private EstadoExpediente estado = EstadoExpediente.ABIERTO;

    @Column(name = "embedding_model_activo", nullable = false, length = 80)
    private String embeddingModelActivo;

    @Column(name = "embedding_dimension", nullable = false)
    private int embeddingDimension;

    @Column(name = "created_by", nullable = false, updatable = false)
    private UUID createdBy;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();

    protected Expediente() {}

    public Expediente(UUID tenantId, String codigo, String titulo, String entidad, TipoExpediente tipo,
                      String modelo, int dimension, UUID createdBy) {
        this.tenantId = tenantId;
        this.codigoExpediente = codigo;
        this.titulo = titulo;
        this.entidadContratante = entidad;
        this.tipoExpediente = tipo;
        this.embeddingModelActivo = modelo;
        this.embeddingDimension = dimension;
        this.createdBy = createdBy;
    }

    public UUID getId() { return id; }
    public UUID getTenantId() { return tenantId; }
    public String getCodigoExpediente() { return codigoExpediente; }
    public String getTitulo() { return titulo; }
    public void setTitulo(String t) { this.titulo = t; }
    public String getEntidadContratante() { return entidadContratante; }
    public void setEntidadContratante(String e) { this.entidadContratante = e; }
    public TipoExpediente getTipoExpediente() { return tipoExpediente; }
    public void setTipoExpediente(TipoExpediente t) { this.tipoExpediente = t; }
    public EstadoExpediente getEstado() { return estado; }
    public void setEstado(EstadoExpediente e) { this.estado = e; }
    public String getEmbeddingModelActivo() { return embeddingModelActivo; }
    public int getEmbeddingDimension() { return embeddingDimension; }
    public UUID getCreatedBy() { return createdBy; }
    public Instant getCreatedAt() { return createdAt; }
}

package co.medtender.api.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.hibernate.annotations.Immutable;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/** Fila de la tabla auditoria (solo anexado: la base rechaza UPDATE y DELETE). */
@Entity
@Immutable
@Table(name = "auditoria")
public class RegistroAuditoria {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "tenant_id") private UUID tenantId;
    @Column(name = "usuario_id") private UUID usuarioId;
    @Column(length = 150) private String email;
    @Column(nullable = false, length = 40) private String accion;
    @Column(nullable = false, length = 12) private String resultado;
    @Column(name = "recurso_tipo", length = 30) private String recursoTipo;
    @Column(name = "recurso_id") private UUID recursoId;
    @Column(length = 64) private String ip;
    @Column(name = "request_id", length = 64) private String requestId;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private Map<String, Object> detalle;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();

    protected RegistroAuditoria() {}

    public RegistroAuditoria(UUID tenantId, UUID usuarioId, String email, String accion, String resultado,
                             String recursoTipo, UUID recursoId, String ip, String requestId,
                             Map<String, Object> detalle) {
        this.tenantId = tenantId;
        this.usuarioId = usuarioId;
        this.email = email;
        this.accion = accion;
        this.resultado = resultado;
        this.recursoTipo = recursoTipo;
        this.recursoId = recursoId;
        this.ip = ip;
        this.requestId = requestId;
        this.detalle = detalle;
    }

    public UUID getId() { return id; }
    public UUID getTenantId() { return tenantId; }
    public UUID getUsuarioId() { return usuarioId; }
    public String getEmail() { return email; }
    public String getAccion() { return accion; }
    public String getResultado() { return resultado; }
    public String getRecursoTipo() { return recursoTipo; }
    public UUID getRecursoId() { return recursoId; }
    public String getIp() { return ip; }
    public String getRequestId() { return requestId; }
    public Map<String, Object> getDetalle() { return detalle; }
    public Instant getCreatedAt() { return createdAt; }
}

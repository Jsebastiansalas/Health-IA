package co.medtender.api.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/** Constancia de que un usuario acepto una version concreta del texto de consentimiento. */
@Entity
@Table(name = "consentimientos")
public class Consentimiento {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "tenant_id", nullable = false, updatable = false)
    private UUID tenantId;

    @Column(name = "usuario_id", nullable = false, updatable = false)
    private UUID usuarioId;

    @Column(nullable = false, length = 30, updatable = false)
    private String version;

    @Column(name = "aceptado_at", nullable = false, updatable = false)
    private Instant aceptadoAt = Instant.now();

    protected Consentimiento() {}

    public Consentimiento(UUID tenantId, UUID usuarioId, String version) {
        this.tenantId = tenantId;
        this.usuarioId = usuarioId;
        this.version = version;
    }

    public UUID getId() { return id; }
    public UUID getTenantId() { return tenantId; }
    public UUID getUsuarioId() { return usuarioId; }
    public String getVersion() { return version; }
    public Instant getAceptadoAt() { return aceptadoAt; }
}

package co.medtender.api.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/** Enlace de verificacion de correo emitido a un usuario. Solo se guarda el hash del token. */
@Entity
@Table(name = "verificaciones_correo")
public class VerificacionCorreo {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "tenant_id", nullable = false, updatable = false)
    private UUID tenantId;

    @Column(name = "usuario_id", nullable = false, updatable = false)
    private UUID usuarioId;

    @Column(name = "token_hash", nullable = false, updatable = false, length = 64)
    private String tokenHash;

    @Column(name = "expira_at", nullable = false, updatable = false)
    private Instant expiraAt;

    @Column(name = "usado_at")
    private Instant usadoAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();

    protected VerificacionCorreo() {}

    public VerificacionCorreo(UUID tenantId, UUID usuarioId, String tokenHash, Instant expiraAt) {
        this.tenantId = tenantId;
        this.usuarioId = usuarioId;
        this.tokenHash = tokenHash;
        this.expiraAt = expiraAt;
    }

    public UUID getId() { return id; }
    public UUID getTenantId() { return tenantId; }
    public UUID getUsuarioId() { return usuarioId; }
    public String getTokenHash() { return tokenHash; }
    public Instant getExpiraAt() { return expiraAt; }
    public Instant getUsadoAt() { return usadoAt; }
    public void marcarUsado() { this.usadoAt = Instant.now(); }
}

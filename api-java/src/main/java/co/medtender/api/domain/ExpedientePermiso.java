package co.medtender.api.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.util.UUID;

@Entity
@Table(name = "expediente_permisos")
public class ExpedientePermiso {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "tenant_id", nullable = false, updatable = false)
    private UUID tenantId;

    @Column(name = "expediente_id", nullable = false, updatable = false)
    private UUID expedienteId;

    @Column(name = "usuario_id", nullable = false, updatable = false)
    private UUID usuarioId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private Permiso permiso;

    protected ExpedientePermiso() {}

    public ExpedientePermiso(UUID tenantId, UUID expedienteId, UUID usuarioId, Permiso permiso) {
        this.tenantId = tenantId;
        this.expedienteId = expedienteId;
        this.usuarioId = usuarioId;
        this.permiso = permiso;
    }

    public UUID getId() { return id; }
    public UUID getTenantId() { return tenantId; }
    public UUID getExpedienteId() { return expedienteId; }
    public UUID getUsuarioId() { return usuarioId; }
    public Permiso getPermiso() { return permiso; }
    public void setPermiso(Permiso p) { this.permiso = p; }
}

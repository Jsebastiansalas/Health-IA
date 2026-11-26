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

@Entity
@Table(name = "usuarios")
public class Usuario {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "tenant_id", nullable = false, updatable = false)
    private UUID tenantId;

    @Column(nullable = false, unique = true, length = 150)
    private String email;

    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    @Column(name = "nombre_completo", nullable = false, length = 150)
    private String nombreCompleto;

    @Enumerated(EnumType.STRING)
    @Column(name = "rol_global", nullable = false, length = 40)
    private RolGlobal rolGlobal;

    @Column(nullable = false)
    private boolean activo = true;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();

    /** Tokens emitidos antes de esta fecha ya no valen (cambio de contraseña, «cerrar todas las sesiones»). */
    @Column(name = "sesiones_validas_desde", nullable = false)
    private Instant sesionesValidasDesde = Instant.EPOCH;

    /** Secreto TOTP cifrado (AES-GCM) y el pendiente de confirmar mientras se activa. */
    @Column(name = "totp_secreto") private String totpSecreto;
    @Column(name = "totp_pendiente") private String totpPendiente;
    @Column(name = "totp_activo", nullable = false) private boolean totpActivo;

    protected Usuario() {}

    public Usuario(UUID tenantId, String email, String passwordHash, String nombreCompleto, RolGlobal rolGlobal) {
        this.tenantId = tenantId;
        this.email = email;
        this.passwordHash = passwordHash;
        this.nombreCompleto = nombreCompleto;
        this.rolGlobal = rolGlobal;
    }

    public UUID getId() { return id; }
    public UUID getTenantId() { return tenantId; }
    public String getEmail() { return email; }
    public String getPasswordHash() { return passwordHash; }
    public String getNombreCompleto() { return nombreCompleto; }
    public void setNombreCompleto(String n) { this.nombreCompleto = n; }
    public RolGlobal getRolGlobal() { return rolGlobal; }
    public void setRolGlobal(RolGlobal r) { this.rolGlobal = r; }
    public boolean isActivo() { return activo; }
    public void setActivo(boolean a) { this.activo = a; }
    public Instant getCreatedAt() { return createdAt; }

    public void setPasswordHash(String h) { this.passwordHash = h; }
    public Instant getSesionesValidasDesde() { return sesionesValidasDesde; }

    /** Invalida todos los tokens emitidos hasta ahora (precisión de milisegundos, como `emitido_ms`). */
    public void invalidarSesiones() {
        this.sesionesValidasDesde = Instant.now().truncatedTo(java.time.temporal.ChronoUnit.MILLIS);
    }

    public String getTotpSecreto() { return totpSecreto; }
    public String getTotpPendiente() { return totpPendiente; }
    public boolean isTotpActivo() { return totpActivo; }
    public void setTotpPendiente(String cifrado) { this.totpPendiente = cifrado; }

    public void activarTotp() {
        this.totpSecreto = this.totpPendiente;
        this.totpPendiente = null;
        this.totpActivo = true;
    }

    public void desactivarTotp() {
        this.totpSecreto = null;
        this.totpPendiente = null;
        this.totpActivo = false;
    }
}

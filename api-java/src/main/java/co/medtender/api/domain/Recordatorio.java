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
import java.time.LocalDate;
import java.util.Map;
import java.util.UUID;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/** Recordatorio de un control que indica un documento. Lo propone el agente y lo confirma la persona. */
@Entity
@Table(name = "recordatorios")
public class Recordatorio {

    public enum Estado { PROPUESTO, CONFIRMADO, HECHO, DESCARTADO }

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "tenant_id", nullable = false, updatable = false) private UUID tenantId;
    @Column(name = "usuario_id", nullable = false, updatable = false) private UUID usuarioId;
    @Column(name = "expediente_id", nullable = false, updatable = false) private UUID expedienteId;
    @Column(nullable = false, length = 300, updatable = false) private String texto;
    @Column(name = "fecha_texto", nullable = false, length = 120, updatable = false) private String fechaTexto;
    @Column(name = "fecha_documento", updatable = false) private LocalDate fechaDocumento;
    @Column(name = "fecha_propuesta", updatable = false) private LocalDate fechaPropuesta;
    @Column private LocalDate fecha;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private Estado estado = Estado.PROPUESTO;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb", updatable = false)
    private Map<String, Object> cita;

    @JdbcTypeCode(SqlTypes.CHAR)
    @Column(nullable = false, length = 64, updatable = false)
    private String clave;

    @Column(name = "aviso_enviado_at") private Instant avisoEnviadoAt;
    @Column(name = "created_at", nullable = false, updatable = false) private Instant createdAt = Instant.now();
    @Column(name = "updated_at", nullable = false) private Instant updatedAt = Instant.now();

    protected Recordatorio() {}

    public Recordatorio(UUID tenantId, UUID usuarioId, UUID expedienteId, String texto, String fechaTexto,
                        LocalDate fechaDocumento, LocalDate fechaPropuesta, Map<String, Object> cita, String clave) {
        this.tenantId = tenantId;
        this.usuarioId = usuarioId;
        this.expedienteId = expedienteId;
        this.texto = texto;
        this.fechaTexto = fechaTexto;
        this.fechaDocumento = fechaDocumento;
        this.fechaPropuesta = fechaPropuesta;
        this.cita = cita;
        this.clave = clave;
    }

    /** Cambia de estado. Confirmar exige fecha; al cambiar la fecha se vuelve a poder avisar. */
    public void actualizar(Estado nuevo, LocalDate nuevaFecha) {
        if (nuevaFecha != null && !nuevaFecha.equals(this.fecha)) {
            this.fecha = nuevaFecha;
            this.avisoEnviadoAt = null;
        }
        this.estado = nuevo;
        this.updatedAt = Instant.now();
    }

    public void marcarAvisado() {
        this.avisoEnviadoAt = Instant.now();
    }

    public UUID getId() { return id; }
    public UUID getTenantId() { return tenantId; }
    public UUID getUsuarioId() { return usuarioId; }
    public UUID getExpedienteId() { return expedienteId; }
    public String getTexto() { return texto; }
    public String getFechaTexto() { return fechaTexto; }
    public LocalDate getFechaDocumento() { return fechaDocumento; }
    public LocalDate getFechaPropuesta() { return fechaPropuesta; }
    public LocalDate getFecha() { return fecha; }
    public Estado getEstado() { return estado; }
    public Map<String, Object> getCita() { return cita; }
    public String getClave() { return clave; }
    public Instant getAvisoEnviadoAt() { return avisoEnviadoAt; }
    public Instant getCreatedAt() { return createdAt; }
}

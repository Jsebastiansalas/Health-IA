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
@Table(name = "tenants")
public class Tenant {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(nullable = false, length = 150)
    private String nombre;

    @Column(nullable = false, unique = true, length = 50)
    private String nit;

    @Enumerated(EnumType.STRING)
    @Column(name = "politica_borrado", nullable = false, length = 30)
    private PoliticaBorrado politicaBorrado = PoliticaBorrado.INMEDIATO;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private TipoTenant tipo = TipoTenant.ORGANIZACION;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();

    protected Tenant() {}

    public Tenant(String nombre, String nit, PoliticaBorrado politicaBorrado) {
        this.nombre = nombre;
        this.nit = nit;
        this.politicaBorrado = politicaBorrado;
    }

    public Tenant(String nombre, String nit, PoliticaBorrado politicaBorrado, TipoTenant tipo) {
        this(nombre, nit, politicaBorrado);
        this.tipo = tipo;
    }

    public TipoTenant getTipo() { return tipo; }
    public UUID getId() { return id; }
    public String getNombre() { return nombre; }
    public void setNombre(String nombre) { this.nombre = nombre; }
    public String getNit() { return nit; }
    public PoliticaBorrado getPoliticaBorrado() { return politicaBorrado; }
    public void setPoliticaBorrado(PoliticaBorrado p) { this.politicaBorrado = p; }
    public Instant getCreatedAt() { return createdAt; }
}

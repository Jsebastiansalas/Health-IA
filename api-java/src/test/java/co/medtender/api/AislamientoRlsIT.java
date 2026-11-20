package co.medtender.api;

import static org.assertj.core.api.Assertions.assertThat;

import co.medtender.api.security.ContextoTenant;
import java.util.UUID;
import javax.sql.DataSource;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * Aislamiento por tenant EN la base de datos (RLS, V8). No pasa por los repositorios: ejecuta SQL
 * sin ningun filtro con la conexion de la aplicacion y comprueba que PostgreSQL solo entrega las
 * filas del tenant declarado.
 */
class AislamientoRlsIT extends IntegracionBase {

    @Autowired DataSource dataSourceApp;

    @AfterEach
    void limpiarContexto() {
        ContextoTenant.limpiar();
    }

    private int usuariosVistosPorLaApp() {
        // Consulta deliberadamente SIN "where tenant_id = ...".
        return new JdbcTemplate(dataSourceApp).queryForObject("select count(*) from usuarios", Integer.class);
    }

    private UUID tenantDe(String nit) {
        return jdbc.queryForObject("select id from tenants where nit = ?", UUID.class, nit);
    }

    @Test
    void sinContextoLaAplicacionNoVeNingunaFila() throws Exception {
        registrarTenant("900111", "a@a.co", "Clave-Segura-123");
        registrarTenant("900222", "b@b.co", "Clave-Segura-123");

        assertThat(jdbc.queryForObject("select count(*) from usuarios", Integer.class)).isEqualTo(2);
        assertThat(usuariosVistosPorLaApp()).isZero();
    }

    @Test
    void cadaTenantVeSoloSusFilasAunqueLaConsultaNoFiltre() throws Exception {
        registrarTenant("900111", "a@a.co", "Clave-Segura-123");
        registrarTenant("900222", "b@b.co", "Clave-Segura-123");

        ContextoTenant.fijarTenant(tenantDe("900111"));
        assertThat(usuariosVistosPorLaApp()).isEqualTo(1);
        var correo = new JdbcTemplate(dataSourceApp).queryForObject("select email from usuarios", String.class);
        assertThat(correo).isEqualTo("a@a.co");

        ContextoTenant.fijarTenant(tenantDe("900222"));
        assertThat(usuariosVistosPorLaApp()).isEqualTo(1);
    }

    @Test
    void elModoSistemaVeTodosLosTenantsYSeRestauraAlSalir() throws Exception {
        registrarTenant("900111", "a@a.co", "Clave-Segura-123");
        registrarTenant("900222", "b@b.co", "Clave-Segura-123");

        int vistos = ContextoTenant.comoSistema(this::usuariosVistosPorLaApp);
        assertThat(vistos).isEqualTo(2);
        assertThat(usuariosVistosPorLaApp()).isZero(); // al salir vuelve a no ver nada
    }

    @Test
    void unaConexionReutilizadaNoArrastraElTenantAnterior() throws Exception {
        registrarTenant("900111", "a@a.co", "Clave-Segura-123");

        ContextoTenant.fijarTenant(tenantDe("900111"));
        assertThat(usuariosVistosPorLaApp()).isEqualTo(1);
        ContextoTenant.limpiar();
        // El pool devuelve (casi seguro) la misma conexion: debe llegar sin contexto.
        assertThat(usuariosVistosPorLaApp()).isZero();
    }

    @Test
    void laAplicacionNoPuedeEscribirEnOtroTenant() throws Exception {
        registrarTenant("900111", "a@a.co", "Clave-Segura-123");
        registrarTenant("900222", "b@b.co", "Clave-Segura-123");
        UUID otro = tenantDe("900222");

        ContextoTenant.fijarTenant(tenantDe("900111"));
        var app = new JdbcTemplate(dataSourceApp);
        org.junit.jupiter.api.Assertions.assertThrows(Exception.class, () -> app.update(
                "insert into usuarios (tenant_id, email, password_hash, nombre_completo, rol_global) "
                        + "values (?, 'intruso@a.co', 'x', 'Intruso', 'LECTOR')", otro));
    }

    @Test
    void elRolDeLaAplicacionNoEsSuperusuarioNiSaltaRls() {
        var fila = jdbc.queryForMap(
                "select rolsuper, rolbypassrls from pg_roles where rolname = 'medtender_app'");
        assertThat(fila.get("rolsuper")).isEqualTo(false);
        assertThat(fila.get("rolbypassrls")).isEqualTo(false);
    }
}

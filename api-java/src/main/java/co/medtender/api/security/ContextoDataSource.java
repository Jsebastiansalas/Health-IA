package co.medtender.api.security;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import javax.sql.DataSource;
import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.jdbc.datasource.DelegatingDataSource;
import org.springframework.stereotype.Component;

/**
 * Cada conexion que sale del pool recibe el contexto de aislamiento de la hebra (app.tenant_id y
 * app.sistema) ANTES de usarse. Se fija SIEMPRE, incluso vacio: una conexion reutilizada jamas
 * arrastra el tenant de la peticion anterior. Con el valor vacio, la base no entrega ninguna fila.
 */
@Component
class ContextoDataSourcePostProcessor implements BeanPostProcessor {

    @Override
    public Object postProcessAfterInitialization(Object bean, String beanName) {
        if (bean instanceof DataSource ds && !(bean instanceof ContextoDataSource) && "dataSource".equals(beanName)) {
            return new ContextoDataSource(ds);
        }
        return bean;
    }
}

class ContextoDataSource extends DelegatingDataSource {

    private static final String SQL =
            "SELECT set_config('app.tenant_id', ?, false), set_config('app.sistema', ?, false)";

    ContextoDataSource(DataSource destino) {
        super(destino);
    }

    @Override
    public Connection getConnection() throws SQLException {
        return preparar(super.getConnection());
    }

    @Override
    public Connection getConnection(String username, String password) throws SQLException {
        return preparar(super.getConnection(username, password));
    }

    private static Connection preparar(Connection c) throws SQLException {
        var ctx = ContextoTenant.actual();
        try (PreparedStatement ps = c.prepareStatement(SQL)) {
            ps.setString(1, ctx.tenantId() == null ? "" : ctx.tenantId().toString());
            ps.setString(2, ctx.sistema() ? "on" : "off");
            ps.execute();
        } catch (SQLException e) {
            c.close();
            throw e;
        }
        return c;
    }
}

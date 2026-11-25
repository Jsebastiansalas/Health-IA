package co.medtender.api.errores;

import com.sun.net.httpserver.HttpServer;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.zip.GZIPInputStream;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;

import static org.assertj.core.api.Assertions.assertThat;

/** El rastreo de errores no puede llevarse datos de salud: se revisan los bytes que de verdad salen. */
class RastreoErroresTest {

    private final List<String> recibidos = new CopyOnWriteArrayList<>();
    private HttpServer colector;
    private RastreoErrores rastreo;

    @BeforeEach
    void iniciar() throws IOException {
        colector = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        colector.createContext("/", ex -> {
            byte[] cuerpo = ex.getRequestBody().readAllBytes();
            if ("gzip".equals(ex.getRequestHeaders().getFirst("Content-Encoding"))) {
                cuerpo = new GZIPInputStream(new ByteArrayInputStream(cuerpo)).readAllBytes();
            }
            recibidos.add(new String(cuerpo, StandardCharsets.UTF_8));
            ex.sendResponseHeaders(200, 2);
            ex.getResponseBody().write("{}".getBytes(StandardCharsets.UTF_8));
            ex.close();
        });
        colector.start();
    }

    @AfterEach
    void apagar() {
        if (rastreo != null) rastreo.apagar();
        colector.stop(0);
        MDC.clear();
    }

    private String dsn() {
        return "http://claveinventada@127.0.0.1:" + colector.getAddress().getPort() + "/1";
    }

    private static void fallaConDatos() {
        throw new IllegalArgumentException("No se encontró la hemoglobina de Ana Pérez (13,2 g/dL)");
    }

    @Test
    void soloViajaElTipoYPorDondePaso() throws Exception {
        rastreo = new RastreoErrores(dsn(), "produccion");
        MDC.put("ip", "190.1.2.3");
        MDC.put("usuario", "ana@correo.co");
        var log = LoggerFactory.getLogger(RastreoErroresTest.class);
        try {
            fallaConDatos();
        } catch (IllegalArgumentException e) {
            log.error("Falló la consulta de {}", "ana@correo.co", new IllegalStateException("expediente «Historia de Ana»", e));
        }
        rastreo.vaciar();

        String todo = String.join("\n", recibidos);
        assertThat(todo).contains("IllegalStateException", "IllegalArgumentException", "fallaConDatos", "RastreoErroresTest");
        assertThat(todo).doesNotContain("Ana", "ana@correo.co", "hemoglobina", "13,2", "Historia", "Falló la consulta", "190.1.2.3");
        assertThat(todo).doesNotContain(InetAddress.getLocalHost().getHostName(), "user.name", System.getProperty("user.name"));
        assertThat(todo).contains("\"server_name\":\"api\"");
    }

    @Test
    void unErrorSinExcepcionNoSeReportaYSinDsnNoHaceNada() {
        rastreo = new RastreoErrores(dsn(), "produccion");
        LoggerFactory.getLogger(RastreoErroresTest.class).error("algo sobre Ana Pérez");
        rastreo.vaciar();
        assertThat(recibidos).isEmpty();
        rastreo.apagar();

        var apagado = new RastreoErrores("", "produccion");
        LoggerFactory.getLogger(RastreoErroresTest.class).error("x", new RuntimeException("Ana"));
        apagado.vaciar();
        assertThat(recibidos).isEmpty();
    }
}

package co.medtender.api;

import com.sun.net.httpserver.HttpServer;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.EOFException;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

/** Infraestructura compartida por todas las pruebas de integracion (una sola vez por JVM). */
public final class Infra {

    public static final String JWT_SECRET = "secreto-de-pruebas-0123456789-abcdefghij-XYZ";
    public static final String METRICS_TOKEN = "token-metricas-de-prueba";
    public static final String AGENTE_TOKEN = "token-interno-de-prueba";
    public static final String EICAR = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*";

    static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer(
            DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"));
    static final GenericContainer<?> REDIS = new GenericContainer<>(DockerImageName.parse("redis:7-alpine"))
            .withExposedPorts(6379);

    public static final ClamdFalso CLAMD = new ClamdFalso();
    public static final AgenteFalso AGENTE = new AgenteFalso();
    public static final Path EFIMERO;

    static {
        try {
            EFIMERO = Files.createTempDirectory("medtender-efimero-test");
            POSTGRES.start();
            REDIS.start();
            CLAMD.iniciar();
            AGENTE.iniciar();
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    private Infra() {}

    public static void registrar(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        r.add("spring.datasource.username", POSTGRES::getUsername);
        r.add("spring.datasource.password", POSTGRES::getPassword);
        r.add("spring.data.redis.url", () -> "redis://" + REDIS.getHost() + ":" + REDIS.getMappedPort(6379));
        r.add("medtender.jwt.secret", () -> JWT_SECRET);
        r.add("medtender.metrics-token", () -> METRICS_TOKEN);
        r.add("medtender.rate-limit.login-fallos-par", () -> "3");
        r.add("medtender.rate-limit.login-ip-min", () -> "1000");
        r.add("medtender.rate-limit.general-ip-min", () -> "100000");
        r.add("medtender.ingesta.ephemeral-dir", EFIMERO::toString);
        r.add("medtender.ingesta.max-upload-mb", () -> "1");
        r.add("medtender.ingesta.antivirus.host", () -> "127.0.0.1");
        r.add("medtender.ingesta.antivirus.port", () -> Integer.toString(CLAMD.puerto()));
        r.add("medtender.ingesta.antivirus.timeout-s", () -> "5");
        r.add("medtender.ingesta.agente.url", () -> "http://127.0.0.1:" + AGENTE.puerto());
        r.add("medtender.ingesta.agente.token", () -> AGENTE_TOKEN);
        r.add("medtender.ingesta.agente.reintentos", () -> "3");
        r.add("medtender.ingesta.agente.retroceso-ms", () -> "10");
    }

    // ------------------------------------------------------------------------------------------
    /** clamd de mentira: habla el protocolo INSTREAM real y detecta la cadena EICAR. */
    public static final class ClamdFalso {
        private ServerSocket servidor;
        private final AtomicBoolean disponible = new AtomicBoolean(true);

        void iniciar() throws IOException {
            servidor = new ServerSocket(0);
            Thread t = new Thread(this::atender, "clamd-falso");
            t.setDaemon(true);
            t.start();
        }

        public int puerto() {
            return servidor.getLocalPort();
        }

        public void disponible(boolean valor) {
            disponible.set(valor);
        }

        private void atender() {
            while (!servidor.isClosed()) {
                try {
                    Socket s = servidor.accept();
                    Thread h = new Thread(() -> responder(s), "clamd-falso-conexion");
                    h.setDaemon(true);
                    h.start();
                } catch (IOException e) {
                    return;
                }
            }
        }

        private void responder(Socket s) {
            try (s) {
                if (!disponible.get()) {
                    return; // cierra sin responder
                }
                DataInputStream in = new DataInputStream(s.getInputStream());
                byte[] orden = new byte[10];
                in.readFully(orden);
                if (!new String(orden, StandardCharsets.US_ASCII).equals("zINSTREAM\0")) {
                    s.getOutputStream().write("UNKNOWN COMMAND\0".getBytes(StandardCharsets.US_ASCII));
                    return;
                }
                ByteArrayOutputStream contenido = new ByteArrayOutputStream();
                while (true) {
                    int n = in.readInt();
                    if (n == 0) {
                        break;
                    }
                    byte[] bloque = new byte[n];
                    in.readFully(bloque);
                    contenido.write(bloque);
                }
                boolean infectado = contenido.toString(StandardCharsets.ISO_8859_1).contains("EICAR-STANDARD-ANTIVIRUS-TEST-FILE");
                String respuesta = infectado ? "stream: Eicar-Test-Signature FOUND\0" : "stream: OK\0";
                s.getOutputStream().write(respuesta.getBytes(StandardCharsets.US_ASCII));
            } catch (EOFException ignorado) {
                // el cliente cerro
            } catch (IOException ignorado) {
                // sin importancia en pruebas
            }
        }
    }

    // ------------------------------------------------------------------------------------------
    /** Agente de IA de mentira: registra las entregas y responde con el codigo configurado. */
    public static final class AgenteFalso {
        public record Llamada(String ruta, String token) {}

        private HttpServer servidor;
        private final AtomicInteger respuesta = new AtomicInteger(202);
        private final List<Llamada> llamadas = new CopyOnWriteArrayList<>();

        void iniciar() throws IOException {
            servidor = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            servidor.createContext("/internal/v1/documentos/", ex -> {
                llamadas.add(new Llamada(ex.getRequestURI().getPath(), ex.getRequestHeaders().getFirst("X-Internal-Token")));
                ex.getRequestBody().readAllBytes();
                ex.sendResponseHeaders(respuesta.get(), -1);
                ex.close();
            });
            servidor.start();
        }

        public int puerto() {
            return servidor.getAddress().getPort();
        }

        public void responderCon(int codigo) {
            respuesta.set(codigo);
        }

        public List<Llamada> llamadas() {
            return llamadas;
        }

        public void reiniciar() {
            respuesta.set(202);
            llamadas.clear();
        }
    }
}

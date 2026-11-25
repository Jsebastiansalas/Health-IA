package co.medtender.api.auth;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/** Contraseñas filtradas por k-anonimato (sin la red real) y el algoritmo TOTP contra el vector del RFC 6238. */
class PoliticaContrasenaTest {

    @Test
    void soloViajaElPrefijoDelHashYSeDetectaLaFiltrada() throws Exception {
        String filtrada = "Clave-Filtrada-2024";
        String sha1 = HexFormat.of().withUpperCase().formatHex(MessageDigest.getInstance("SHA-1").digest(filtrada.getBytes(StandardCharsets.UTF_8)));
        AtomicReference<String> pedido = new AtomicReference<>();
        HttpServer servidor = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        servidor.createContext("/range/", ex -> {
            pedido.set(ex.getRequestURI().getPath());
            byte[] cuerpo = (sha1.substring(5) + ":42\r\n0000000000000000000000000000000000A:0\r\n").getBytes(StandardCharsets.UTF_8);
            ex.sendResponseHeaders(200, cuerpo.length);
            ex.getResponseBody().write(cuerpo);
            ex.close();
        });
        servidor.start();
        try {
            var p = new PoliticaContrasena(true, "http://127.0.0.1:" + servidor.getAddress().getPort() + "/range/");
            assertThat(p.filtrada(filtrada)).isTrue();
            assertThat(pedido.get()).isEqualTo("/range/" + sha1.substring(0, 5)).doesNotContain(sha1.substring(5));
            assertThat(p.filtrada("Otra-Clave-Que-No-Esta-77")).isFalse();
        } finally {
            servidor.stop(0);
        }
    }

    @Test
    void siElServicioNoRespondeNoSeBloquea() {
        var p = new PoliticaContrasena(true, "http://127.0.0.1:1/range/");
        assertThat(p.filtrada("Clave-Cualquiera-123")).isFalse();
    }

    @Test
    void totpCoincideConElVectorDelRfc6238() {
        // Secreto ASCII "12345678901234567890" en base32; T = 59 s → 94287082 (8 dígitos) → 287082 con 6.
        String secreto = Totp.base32("12345678901234567890".getBytes(StandardCharsets.US_ASCII));
        assertThat(Totp.codigoActual(secreto, Instant.ofEpochSecond(59))).isEqualTo("287082");
        assertThat(Totp.valido(secreto, "287082", Instant.ofEpochSecond(59 + 30))).isTrue(); // un paso de desfase
        assertThat(Totp.valido(secreto, "287082", Instant.ofEpochSecond(59 + 90))).isFalse();
    }
}

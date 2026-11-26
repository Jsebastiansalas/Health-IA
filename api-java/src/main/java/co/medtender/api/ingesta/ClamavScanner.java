package co.medtender.api.ingesta;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Cliente del protocolo INSTREAM de clamd por TCP, sin dependencias externas:
 * {@code zINSTREAM\0} + [longitud big-endian de 4 bytes + bloque]* + {@code 0x00000000}.
 * Respuesta: "stream: OK" | "stream: firma FOUND" | "... ERROR".
 */
public class ClamavScanner implements VirusScanner {

    private static final int BLOQUE = 64 * 1024;

    private final String host;
    private final int puerto;
    private final int timeoutMs;

    public ClamavScanner(String host, int puerto, int timeoutS) {
        this.host = host;
        this.puerto = puerto;
        this.timeoutMs = timeoutS * 1000;
    }

    @Override
    public ResultadoEscaneo escanear(Path ruta) throws AntivirusNoDisponibleException {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(host, puerto), Math.min(timeoutMs, 10_000));
            socket.setSoTimeout(timeoutMs);
            OutputStream out = socket.getOutputStream();
            out.write("zINSTREAM\0".getBytes(StandardCharsets.US_ASCII));
            byte[] buffer = new byte[BLOQUE];
            try (InputStream in = Files.newInputStream(ruta)) {
                int n;
                while ((n = in.read(buffer)) > 0) {
                    out.write(ByteBuffer.allocate(4).putInt(n).array());
                    out.write(buffer, 0, n);
                }
            }
            out.write(new byte[] {0, 0, 0, 0});
            out.flush();
            String respuesta = new String(socket.getInputStream().readNBytes(4096), StandardCharsets.UTF_8)
                    .replaceAll("[\\u0000\\n]+$", "").trim();
            if (respuesta.endsWith("OK")) {
                return ResultadoEscaneo.ok();
            }
            if (respuesta.endsWith("FOUND")) {
                String firma = respuesta.replaceFirst("^stream:", "").replaceFirst("FOUND$", "").trim();
                return ResultadoEscaneo.virus(firma);
            }
            // "INSTREAM size limit exceeded", errores de clamd, etc.: no se acepta el archivo.
            throw new AntivirusNoDisponibleException("Respuesta inesperada de clamd: " + respuesta);
        } catch (IOException e) {
            throw new AntivirusNoDisponibleException("clamd no responde: " + e.getMessage(), e);
        }
    }
}

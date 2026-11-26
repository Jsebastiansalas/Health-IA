package co.medtender.api.push;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.List;
import java.util.Locale;

/**
 * La direccion de envio la entrega el navegador, es decir, el cliente. Solo se acepta si es de un servicio de
 * push conocido: sin esto, cualquiera podria hacer que el servidor llame a su red interna.
 */
public final class DestinoPush {

    private static final List<String> EXACTOS = List.of("fcm.googleapis.com", "web.push.apple.com");
    private static final List<String> DOMINIOS = List.of(".push.services.mozilla.com", ".push.apple.com", ".notify.windows.com");

    private DestinoPush() {}

    public static boolean permitido(String endpoint) {
        if (endpoint == null || endpoint.length() > 1000) return false;
        try {
            URI u = new URI(endpoint);
            String host = u.getHost() == null ? "" : u.getHost().toLowerCase(Locale.ROOT);
            return "https".equals(u.getScheme()) && u.getRawUserInfo() == null && (u.getPort() == -1 || u.getPort() == 443)
                    && (EXACTOS.contains(host) || DOMINIOS.stream().anyMatch(host::endsWith));
        } catch (URISyntaxException e) {
            return false;
        }
    }
}

package co.medtender.api.web;

import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

/** Escribe errores JSON {"detail": "..."} desde filtros, donde no llega el manejador de MVC. */
public final class RespuestaError {

    private RespuestaError() {}

    public static void escribir(HttpServletResponse resp, int estado, String detalle) throws IOException {
        resp.setStatus(estado);
        resp.setContentType("application/json");
        resp.setCharacterEncoding(StandardCharsets.UTF_8.name());
        resp.getWriter().write("{\"detail\":\"" + detalle.replace("\\", "\\\\").replace("\"", "\\\"") + "\"}");
    }
}

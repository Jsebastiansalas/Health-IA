package co.medtender.api.web;

import java.util.Map;
import org.springframework.http.HttpStatus;

/**
 * Error de negocio con el codigo HTTP y el contenido del campo {@code detail}. Normalmente es un
 * texto; algunos errores (duplicados, rechazo de PDF) incluyen datos adicionales.
 */
public class ApiException extends RuntimeException {

    private final HttpStatus estado;
    private final transient Object detalle;
    private final transient Map<String, Object> extra;

    public ApiException(HttpStatus estado, String detalle) {
        super(detalle);
        this.estado = estado;
        this.detalle = detalle;
        this.extra = Map.of();
    }

    /** Detalle estructurado (p. ej. {"msg": "...", "documento_id": "..."}). */
    public ApiException(HttpStatus estado, Map<String, Object> detalle) {
        super(String.valueOf(detalle.get("msg")));
        this.estado = estado;
        this.detalle = detalle;
        this.extra = Map.of();
    }

    /** Respuesta con texto en {@code detail} y claves adicionales al mismo nivel (p. ej. "documento"). */
    public ApiException(HttpStatus estado, String detalle, Map<String, Object> extra) {
        super(detalle);
        this.estado = estado;
        this.detalle = detalle;
        this.extra = extra;
    }

    public HttpStatus getEstado() {
        return estado;
    }

    public Object getDetalle() {
        return detalle;
    }

    public Map<String, Object> getExtra() {
        return extra;
    }
}

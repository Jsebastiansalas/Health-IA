package co.medtender.api.web;

import org.springframework.http.HttpStatus;

/** Error de negocio con el codigo HTTP y el mensaje que ve el cliente (campo {@code detail}). */
public class ApiException extends RuntimeException {

    private final HttpStatus estado;

    public ApiException(HttpStatus estado, String detalle) {
        super(detalle);
        this.estado = estado;
    }

    public HttpStatus getEstado() {
        return estado;
    }
}

package co.medtender.api.web;

import co.medtender.api.limites.LimiteExcedidoException;
import java.util.Map;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

/** Todos los errores salen como {"detail": "..."}, el formato que consume el frontend. */
@RestControllerAdvice
public class ManejadorErrores {

    private static final Logger log = LoggerFactory.getLogger(ManejadorErrores.class);

    private static ResponseEntity<Map<String, String>> de(HttpStatus estado, String detalle) {
        return ResponseEntity.status(estado).body(Map.of("detail", detalle));
    }

    @ExceptionHandler(ApiException.class)
    ResponseEntity<Map<String, Object>> api(ApiException e) {
        var cuerpo = new java.util.LinkedHashMap<String, Object>();
        cuerpo.put("detail", e.getDetalle());
        cuerpo.putAll(e.getExtra());
        return ResponseEntity.status(e.getEstado()).body(cuerpo);
    }

    @ExceptionHandler(org.springframework.web.multipart.MaxUploadSizeExceededException.class)
    ResponseEntity<Map<String, String>> demasiadoGrande(org.springframework.web.multipart.MaxUploadSizeExceededException e) {
        return de(HttpStatus.PAYLOAD_TOO_LARGE, "El archivo supera el tamaño máximo permitido");
    }

    @ExceptionHandler(LimiteExcedidoException.class)
    ResponseEntity<Map<String, String>> limite(LimiteExcedidoException e) {
        return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS)
                .header(HttpHeaders.RETRY_AFTER, Integer.toString(e.getReintentarEnS()))
                .body(Map.of("detail", e.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<Map<String, String>> validacion(MethodArgumentNotValidException e) {
        String detalle = e.getBindingResult().getFieldErrors().stream()
                .map(f -> f.getField() + ": " + f.getDefaultMessage())
                .collect(Collectors.joining("; "));
        return de(HttpStatus.UNPROCESSABLE_ENTITY, detalle.isEmpty() ? "Solicitud inválida" : detalle);
    }

    @ExceptionHandler(HandlerMethodValidationException.class)
    ResponseEntity<Map<String, String>> parametros(HandlerMethodValidationException e) {
        return de(HttpStatus.UNPROCESSABLE_ENTITY, "Parámetros inválidos");
    }

    @ExceptionHandler({HttpMessageNotReadableException.class, MethodArgumentTypeMismatchException.class,
            MissingServletRequestParameterException.class})
    ResponseEntity<Map<String, String>> cuerpo(Exception e) {
        return de(HttpStatus.UNPROCESSABLE_ENTITY, "Solicitud inválida");
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    ResponseEntity<Map<String, String>> metodo(HttpRequestMethodNotSupportedException e) {
        return de(HttpStatus.METHOD_NOT_ALLOWED, "Método no permitido");
    }

    @ExceptionHandler(NoResourceFoundException.class)
    ResponseEntity<Map<String, String>> noEncontrado(NoResourceFoundException e) {
        return de(HttpStatus.NOT_FOUND, "No encontrado");
    }

    @ExceptionHandler(Exception.class)
    ResponseEntity<Map<String, String>> inesperado(Exception e) {
        // AccessDeniedException y AuthenticationException las resuelve Spring Security (403/401).
        if (e instanceof org.springframework.security.access.AccessDeniedException ade) {
            throw ade;
        }
        log.error("Error no controlado", e);
        return de(HttpStatus.INTERNAL_SERVER_ERROR, "Error interno");
    }
}

package co.medtender.api.privacidad;

import co.medtender.api.web.ApiException;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Sin sesion: la portada y la pagina de privacidad nombran al proveedor de IA que esta activo. */
@RestController
@RequestMapping("/api/v1/publico")
public class ProveedorIaController {

    public record ProveedorOut(String proveedor, String respaldo) {}

    private final ProveedorIaService proveedores;

    public ProveedorIaController(ProveedorIaService proveedores) {
        this.proveedores = proveedores;
    }

    @GetMapping("/ia")
    public ProveedorOut proveedor() {
        return proveedores.actual()
                .map(p -> new ProveedorOut(p.principal(), p.respaldo()))
                .orElseThrow(() -> new ApiException(HttpStatus.SERVICE_UNAVAILABLE,
                        "No se pudo comprobar el proveedor de IA activo"));
    }
}

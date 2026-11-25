package co.medtender.api;

import org.junit.jupiter.api.Test;
import org.springframework.test.context.TestPropertySource;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * El correo no decide si la API está viva: con el proveedor caído o sin configurar, se sigue pudiendo ingresar y
 * consultar. (Si contara, Docker la marcaría «unhealthy» y ni el agente ni la web arrancarían.)
 */
@TestPropertySource(properties = {"spring.mail.host=127.0.0.1", "spring.mail.port=1"})
class SaludSinCorreoIT extends IntegracionBase {

    @Test
    void conElCorreoCaidoLaApiSigueSana() throws Exception {
        mvc.perform(get("/health")).andExpect(status().isOk());
    }
}

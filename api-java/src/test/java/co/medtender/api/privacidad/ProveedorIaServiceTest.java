package co.medtender.api.privacidad;

import co.medtender.api.ingesta.AgenteClient;
import co.medtender.api.web.ApiException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.reset;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/** Si no se sabe con certeza qué proveedor recibe los datos, no se supone ninguno. */
class ProveedorIaServiceTest {

    private final AgenteClient agente = mock(AgenteClient.class);

    private void agenteResponde(String proveedor, String respaldo) throws Exception {
        JsonNode r = new ObjectMapper().readTree("{\"proveedor\":\"" + proveedor + "\",\"respaldo\":\"" + respaldo + "\"}");
        reset(agente);
        when(agente.get(eq("/internal/v1/ia"), anyMap())).thenReturn(r);
    }

    private void agenteFalla() {
        reset(agente);
        when(agente.get(eq("/internal/v1/ia"), anyMap()))
                .thenThrow(new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "sin servicio"));
    }

    @Test
    void sinHaberRespondidoNuncaNoHayProveedor() {
        agenteFalla();
        assertThat(new ProveedorIaService(agente, 0).actual()).isEmpty();
    }

    @Test
    void siElAgenteSeCaeSeConservaLoUltimoQueDijo() throws Exception {
        var servicio = new ProveedorIaService(agente, 0);
        agenteResponde("vertex", "claude");
        assertThat(servicio.actual()).contains(new ProveedorIaService.Proveedor("vertex", "claude"));
        agenteFalla(); // caído no envía datos a nadie
        assertThat(servicio.actual()).contains(new ProveedorIaService.Proveedor("vertex", "claude"));
    }

    @Test
    void unProveedorDesconocidoNoSeDisfrazaConElAnterior() throws Exception {
        var servicio = new ProveedorIaService(agente, 0);
        agenteResponde("vertex", "");
        assertThat(servicio.actual()).isPresent();
        agenteResponde("otro_proveedor", "");
        assertThat(servicio.actual()).isEmpty();
        agenteResponde("vertex", "otro_respaldo");
        assertThat(servicio.actual()).isEmpty();
        agenteFalla();
        assertThat(servicio.actual()).isEmpty();
    }

    @Test
    void dentroDelPlazoNoSeVuelveAPreguntar() throws Exception {
        var servicio = new ProveedorIaService(agente, 60);
        agenteResponde("gemini_api", "");
        servicio.actual();
        servicio.actual();
        verify(agente, times(1)).get(eq("/internal/v1/ia"), anyMap());
    }
}

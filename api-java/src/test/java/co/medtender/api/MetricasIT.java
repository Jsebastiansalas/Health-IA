package co.medtender.api;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** Lo que las alertas y el panel esperan encontrar en /metrics de la API. */
class MetricasIT extends IntegracionBase {

    @Test
    void publicaLasCubetasDeLatenciaYElPoolDeConexiones() throws Exception {
        mvc.perform(get("/api/v1/publico/ia")).andExpect(status().isOk());
        String metricas = mvc.perform(get("/metrics").header("Authorization", "Bearer " + METRICS_TOKEN))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        assertThat(metricas).containsPattern("http_server_requests_seconds_bucket\\{[^}]*application=\"medtender-api\"[^}]*le=\"2\\.0\"");
        assertThat(metricas).contains("hikaricp_connections_active", "hikaricp_connections_pending");
    }
}

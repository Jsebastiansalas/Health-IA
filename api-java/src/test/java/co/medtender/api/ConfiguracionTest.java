package co.medtender.api;

import co.medtender.api.config.MedtenderProperties;
import co.medtender.api.config.MedtenderProperties.Jwt;
import co.medtender.api.config.MedtenderProperties.RateLimit;
import java.util.List;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ConfiguracionTest {

    private static MedtenderProperties con(String secreto, boolean signup, boolean proxy, String token, String backend) {
        return new MedtenderProperties("produccion", proxy, new Jwt(secreto, 30, 7), signup,
                List.of("https://app.hospital.co"), token,
                new RateLimit(true, backend, 600, 20, 5, 900, 5, 60, 20, 500, 60, 6));
    }

    @Test
    void configuracionSeguraNoTieneProblemasFatales() {
        var p = con("a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6", false, true, "tok", "redis").problemas();
        assertThat(p.get(0)).isEmpty();
        assertThat(p.get(1)).isEmpty();
    }

    @Test
    void secretoCortoOSimpleEsFatal() {
        assertThat(con("corto", false, true, "t", "redis").problemas().get(0)).isNotEmpty();
        assertThat(con("cambia-esto-por-un-secreto-largo-1234", false, true, "t", "redis").problemas().get(0)).isNotEmpty();
        assertThat(con("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", false, true, "t", "redis").problemas().get(0)).isNotEmpty();
    }

    @Test
    void registroAbiertoMetricasVaciasYMemoriaDanAvisos() {
        var avisos = con("a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6", true, false, "", "memoria").problemas().get(1);
        assertThat(avisos).hasSize(4);
    }
}

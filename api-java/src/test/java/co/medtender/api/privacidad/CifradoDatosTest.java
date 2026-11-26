package co.medtender.api.privacidad;

import tools.jackson.databind.ObjectMapper;
import java.util.Base64;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** La API lee el historial que cifra el agente: los valores de ejemplo los produjo el código de Python. */
class CifradoDatosTest {

    private static final String CLAVE = "Y2xhdmUtZGUtcHJ1ZWJhcy1kZS0zMi1ieXRlcy1vayE=";
    private static final String PREGUNTA =
            "mtd1:U8IknwtEVCmpVmCN28hvegxsSy7iWTohvefpMJRvHhJ42eVRqaoPy1Zq8L//Aor1IU0c00yyPPWSYH2sDDsv+vG9nvRQhZI=";
    private static final String RESPUESTA = "mtd1:OBOGCbke/NBRGppErnHA+JlxfO/bCGaCrIJUdCoR8EIiXM/Q0MLgK+r5MkzrVE28QWsB+hGk"
            + "yCMZT2/Teg2tM5BqfZEBbXGhARrbiwQjLEHqvDtHMRImsoIla1Spug==";

    private final ObjectMapper json = new ObjectMapper();

    @Test
    void leeLoQueCifraElAgente() throws Exception {
        var c = new CifradoDatos(CLAVE, json);
        assertThat(c.texto(PREGUNTA)).isEqualTo("¿Cómo está mi hemoglobina? — año 2026");
        var envoltura = json.createObjectNode().put("cifrado", RESPUESTA).put("huella", "h");
        assertThat(c.respuesta(envoltura).get("respuestaAnalitica").asString())
                .isEqualTo("Está en 13,2 g/dL, según la página 2.");
    }

    @Test
    void loGuardadoSinCifrarPasaIgual() throws Exception {
        var c = new CifradoDatos("", json);
        assertThat(c.texto("¿Qué dice mi examen?")).isEqualTo("¿Qué dice mi examen?");
        var claro = json.readTree("{\"respuestaAnalitica\":\"x\",\"huella\":\"h\"}");
        assertThat(c.respuesta(claro)).isEqualTo(claro);
        // Un «cifrado» que no es texto tampoco es un sobre: Jackson 3 lanza si se lee como texto sin valor por defecto.
        var sinSobre = json.readTree("{\"cifrado\":{\"algo\":1}}");
        assertThat(c.respuesta(sinSobre)).isEqualTo(sinSobre);
    }

    @Test
    void sinClaveOConOtraNoSeEntregaElTextoCifrado() {
        assertThatThrownBy(() -> new CifradoDatos("", json).texto(PREGUNTA)).isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("DATOS_CLAVE");
        String otra = Base64.getEncoder().encodeToString("o".repeat(32).getBytes());
        assertThatThrownBy(() -> new CifradoDatos(otra, json).texto(PREGUNTA)).isInstanceOf(IllegalStateException.class);
    }

    @Test
    void unaClaveMalFormadaImpideArrancar() {
        assertThatThrownBy(() -> new CifradoDatos(Base64.getEncoder().encodeToString("corta".getBytes()), json))
                .isInstanceOf(IllegalStateException.class).hasMessageContaining("32 bytes");
    }
}

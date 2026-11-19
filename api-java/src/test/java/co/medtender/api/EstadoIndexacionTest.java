package co.medtender.api;

import co.medtender.api.domain.Documento;
import co.medtender.api.domain.EstadoIndexacion;
import co.medtender.api.domain.TipoDocumento;
import co.medtender.api.ingesta.DocumentoDtos.DocumentoOut;
import java.util.UUID;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class EstadoIndexacionTest {

    private static Documento nuevo() {
        return new Documento(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), "a.pdf", TipoDocumento.PLIEGO, 0,
                "0".repeat(64), 10, "gemini-embedding-001");
    }

    @Test
    void elCaminoFelizEsLineal() {
        Documento d = nuevo();
        d.transicionar(EstadoIndexacion.VALIDANDO);
        d.transicionar(EstadoIndexacion.EN_COLA);
        d.transicionar(EstadoIndexacion.EXTRAYENDO_OCR);
        d.transicionar(EstadoIndexacion.FRAGMENTANDO);
        d.transicionar(EstadoIndexacion.VECTORIZANDO);
        d.transicionar(EstadoIndexacion.INDEXADO_Y_PURGADO);
        assertThat(d.getEstadoIndexacion().esFinal()).isTrue();
    }

    @Test
    void noSePuedeSaltarNiSalirDeUnEstadoFinal() {
        Documento d = nuevo();
        assertThatThrownBy(() -> d.transicionar(EstadoIndexacion.EN_COLA)).isInstanceOf(IllegalStateException.class);
        d.transicionar(EstadoIndexacion.ERROR_PURGADO); // desde cualquier estado no final
        assertThatThrownBy(() -> d.transicionar(EstadoIndexacion.VALIDANDO)).isInstanceOf(IllegalStateException.class);
        assertThatThrownBy(() -> d.transicionar(EstadoIndexacion.ERROR_PURGADO)).isInstanceOf(IllegalStateException.class);
    }

    @Test
    void elProgresoDeVectorizandoAvanzaConLosFragmentos() throws Exception {
        Documento d = nuevo();
        d.transicionar(EstadoIndexacion.VALIDANDO);
        d.transicionar(EstadoIndexacion.EN_COLA);
        d.transicionar(EstadoIndexacion.EXTRAYENDO_OCR);
        d.transicionar(EstadoIndexacion.FRAGMENTANDO);
        d.transicionar(EstadoIndexacion.VECTORIZANDO);
        assertThat(DocumentoOut.de(d, "x").progreso()).isEqualTo(80);
        set(d, "totalChunksEsperados", 100);
        set(d, "totalChunksGuardados", 50);
        assertThat(DocumentoOut.de(d, "x").progreso()).isEqualTo(89); // 80 + 19 * 50 / 100
    }

    @Test
    void avisaCuandoLaVersionDeOcrCambio() throws Exception {
        Documento d = nuevo();
        assertThat(DocumentoOut.de(d, "tesseract-9").avisoOcrDesactualizado()).isFalse(); // sin paginas OCR
        set(d, "paginasOcr", 4);
        assertThat(DocumentoOut.de(d, "tesseract-9").avisoOcrDesactualizado()).isTrue();
        assertThat(DocumentoOut.de(d, "tesseract-5.x-v1").avisoOcrDesactualizado()).isFalse();
    }

    private static void set(Documento d, String campo, Object valor) throws Exception {
        var f = Documento.class.getDeclaredField(campo);
        f.setAccessible(true);
        f.set(d, valor);
    }
}

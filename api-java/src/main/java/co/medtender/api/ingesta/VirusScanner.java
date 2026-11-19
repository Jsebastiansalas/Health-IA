package co.medtender.api.ingesta;

import java.nio.file.Path;

/** Escaneo antivirus enchufable. */
public interface VirusScanner {

    ResultadoEscaneo escanear(Path ruta) throws AntivirusNoDisponibleException;

    record ResultadoEscaneo(boolean limpio, String firma) {
        public static ResultadoEscaneo ok() {
            return new ResultadoEscaneo(true, null);
        }

        public static ResultadoEscaneo virus(String firma) {
            return new ResultadoEscaneo(false, firma);
        }
    }

    class AntivirusNoDisponibleException extends Exception {
        public AntivirusNoDisponibleException(String mensaje, Throwable causa) {
            super(mensaje, causa);
        }

        public AntivirusNoDisponibleException(String mensaje) {
            super(mensaje);
        }
    }
}

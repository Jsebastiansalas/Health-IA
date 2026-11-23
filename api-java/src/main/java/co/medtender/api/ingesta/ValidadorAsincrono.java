package co.medtender.api.ingesta;

import co.medtender.api.domain.DocumentoRepository;
import co.medtender.api.domain.EstadoIndexacion;
import co.medtender.api.domain.MotivoPurga;
import co.medtender.api.security.ContextoTenant;
import java.nio.file.Path;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Validacion posterior a la recepcion (antivirus + estructura) y entrega al agente.
 *
 * <p>Va fuera de la peticion HTTP porque escanear un PDF de cientos de MB puede tardar mas de un
 * minuto; el cliente sigue el progreso con GET .../documentos/{id}. Ninguna conexion de base de
 * datos se mantiene durante el escaneo.
 */
@Service
public class ValidadorAsincrono {

    private static final Logger log = LoggerFactory.getLogger(ValidadorAsincrono.class);

    private final DocumentoRepository documentos;
    private final AlmacenEfimero almacen;
    private final VirusScanner scanner;
    private final InspectorPdf inspector;
    private final PurgaService purga;
    private final AgenteClient agente;
    private final TransactionTemplate tx;

    public ValidadorAsincrono(DocumentoRepository documentos, AlmacenEfimero almacen, VirusScanner scanner,
                              InspectorPdf inspector, PurgaService purga, AgenteClient agente,
                              PlatformTransactionManager tm) {
        this.documentos = documentos;
        this.almacen = almacen;
        this.scanner = scanner;
        this.inspector = inspector;
        this.purga = purga;
        this.agente = agente;
        this.tx = new TransactionTemplate(tm);
    }

    private record Resultado(String motivoRechazo, Integer paginas) {}

    @Async(AsyncConfig.EJECUTOR_VALIDACION)
    public void validarYEncolar(UUID documentoId) {
        // Tarea en segundo plano: no hay peticion ni tenant en esta hebra.
        ContextoTenant.comoSistema(() -> validarYEncolarComoSistema(documentoId));
    }

    private void validarYEncolarComoSistema(UUID documentoId) {
        try {
            var previo = documentos.findById(documentoId).orElse(null);
            if (previo == null || previo.getEstadoIndexacion() != EstadoIndexacion.VALIDANDO) {
                return;
            }

            Resultado r = evaluar(documentoId, previo.getFormato());

            // Se relee: pudo eliminarse o expirar mientras se escaneaba. Que no quede el archivo.
            var actual = documentos.findById(documentoId).orElse(null);
            if (actual == null || actual.getEstadoIndexacion() != EstadoIndexacion.VALIDANDO) {
                almacen.borrarTodo(documentoId);
                return;
            }
            if (r.motivoRechazo() != null) {
                purga.rechazar(documentoId, MotivoPurga.ERROR_VALIDACION, r.motivoRechazo());
                return;
            }
            tx.executeWithoutResult(s -> documentos.buscarParaActualizar(documentoId).ifPresent(d -> {
                d.setTotalPaginas(r.paginas());
                d.transicionar(EstadoIndexacion.EN_COLA);
                documentos.save(d);
            }));
            try {
                agente.encolarProcesamiento(documentoId);
            } catch (AgenteClient.AgenteNoDisponibleException e) {
                log.error("No se pudo entregar el documento {} al agente", documentoId, e);
                purga.fallarYPurgar(documentoId, MotivoPurga.ERROR_PROCESAMIENTO,
                        "El servicio de procesamiento no está disponible; vuelva a cargar el PDF más tarde");
            }
        } catch (Throwable t) {
            // Garantia de borrado tambien para la parte asincrona.
            purga.fallarYPurgar(documentoId, MotivoPurga.ERROR_PROCESAMIENTO,
                    "Error interno en la validación: " + t.getClass().getSimpleName());
            log.error("Error validando documento {}", documentoId, t);
            if (t instanceof Error err) {
                throw err;
            }
        }
    }

    /** Antivirus primero: un archivo malicioso no debe llegar al parser de PDF. No toca la base de datos. */
    private Resultado evaluar(UUID documentoId, co.medtender.api.domain.FormatoDocumento formato) {
        Path ruta = almacen.rutaDocumento(documentoId, formato);
        long t0 = System.nanoTime();
        VirusScanner.ResultadoEscaneo escaneo;
        try {
            escaneo = scanner.escanear(ruta);
        } catch (VirusScanner.AntivirusNoDisponibleException e) {
            log.error("Antivirus no disponible documento={}: {}", documentoId, e.getMessage());
            return new Resultado("El antivirus no está disponible; vuelva a cargar el documento más tarde", null);
        }
        double segAv = (System.nanoTime() - t0) / 1e9;
        if (!escaneo.limpio()) {
            log.warn("Virus detectado documento={} firma={}", documentoId, escaneo.firma());
            return new Resultado("Archivo rechazado por el antivirus: " + escaneo.firma(), null);
        }
        t0 = System.nanoTime();
        try {
            int paginas = formato.esImagen() ? inspector.inspeccionarImagen(ruta, formato) : inspector.inspeccionar(ruta);
            log.info("Validacion documento={} antivirus={}s estructura={}s paginas={}", documentoId,
                    String.format("%.1f", segAv), String.format("%.1f", (System.nanoTime() - t0) / 1e9), paginas);
            return new Resultado(null, paginas);
        } catch (InspectorPdf.PdfInvalidoException e) {
            return new Resultado(e.getMessage(), null);
        }
    }
}

package co.medtender.api.ingesta;

import co.medtender.api.domain.ActaPurga;
import co.medtender.api.domain.ActaPurgaRepository;
import co.medtender.api.domain.Documento;
import co.medtender.api.domain.DocumentoRepository;
import co.medtender.api.domain.EstadoIndexacion;
import co.medtender.api.domain.MotivoPurga;
import java.util.Optional;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Borrado fisico garantizado y Acta de Purga para los documentos que Java RECHAZA antes de
 * entregarlos al agente (no es PDF, virus, cifrado, corrupto, error interno) y para los que se
 * eliminan a mano. La purga tras una indexacion exitosa la hace el agente Python, que es quien
 * verifica el conteo de vectores.
 *
 * <p>El archivo se borra ANTES de la transaccion: si la base de datos falla, la confidencialidad
 * ya esta a salvo y el barrido del agente corregira el estado del documento.
 */
@Service
public class PurgaService {

    private static final Logger log = LoggerFactory.getLogger(PurgaService.class);

    private final DocumentoRepository documentos;
    private final ActaPurgaRepository actas;
    private final AlmacenEfimero almacen;
    private final TransactionTemplate tx;

    public PurgaService(DocumentoRepository documentos, ActaPurgaRepository actas, AlmacenEfimero almacen,
                        PlatformTransactionManager tm) {
        this.documentos = documentos;
        this.actas = actas;
        this.almacen = almacen;
        this.tx = new TransactionTemplate(tm);
    }

    /**
     * Borra el PDF, deja el documento en ERROR_PURGADO con su motivo y registra el acta.
     * Si el documento ya no existe o ya es final, solo se asegura de que no quede ningun archivo.
     */
    public Optional<Documento> rechazar(UUID documentoId, MotivoPurga motivo, String detalle) {
        boolean existia = almacen.borrarTodo(documentoId);
        return Optional.ofNullable(tx.execute(status -> {
            Documento d = documentos.buscarParaActualizar(documentoId).orElse(null);
            if (d == null || d.getEstadoIndexacion().esFinal()) {
                return d;
            }
            d.transicionar(EstadoIndexacion.ERROR_PURGADO);
            d.marcarPurgado(detalle);
            documentos.save(d);
            actas.save(new ActaPurga(d.getTenantId(), d.getId(), d.getSha256Original(), motivo,
                    d.getTotalChunksEsperados(), 0, existia, detalle));
            log.info("Purga {} documento={} archivo_existia={}", motivo, documentoId, existia);
            return d;
        }));
    }

    /**
     * Para bloques catch: nunca lanza. Si la base de datos no esta disponible el archivo igual se
     * borra (ultimo recurso).
     */
    public void fallarYPurgar(UUID documentoId, MotivoPurga motivo, String detalle) {
        try {
            rechazar(documentoId, motivo, detalle);
        } catch (RuntimeException e) {
            try {
                almacen.borrarTodo(documentoId);
            } catch (RuntimeException ignorado) {
                log.error("No se pudo borrar el archivo residual del documento {}", documentoId, ignorado);
            }
            log.error("No se pudo registrar la purga del documento {}", documentoId, e);
        }
    }

    /** Eliminacion manual: borra archivos, deja un acta y elimina el documento (y sus fragmentos por cascada). */
    public void eliminar(Documento documento, String eliminadoPor) {
        boolean existia = almacen.borrarTodo(documento.getId());
        tx.executeWithoutResult(status -> {
            actas.saveAndFlush(new ActaPurga(documento.getTenantId(), documento.getId(),
                    documento.getSha256Original(), MotivoPurga.DOCUMENTO_ELIMINADO,
                    documento.getTotalChunksEsperados(), documento.getTotalChunksGuardados(), existia,
                    "Eliminado por " + eliminadoPor));
            documentos.deleteById(documento.getId());
        });
    }
}

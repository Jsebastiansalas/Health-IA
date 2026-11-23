package co.medtender.api.ingesta;

import co.medtender.api.auditoria.Accion;
import co.medtender.api.auditoria.AuditoriaService;
import co.medtender.api.config.IngestaProperties;
import co.medtender.api.config.MedtenderProperties;
import co.medtender.api.domain.ActaPurgaRepository;
import co.medtender.api.domain.Documento;
import co.medtender.api.domain.DocumentoRepository;
import co.medtender.api.domain.EstadoExpediente;
import co.medtender.api.domain.EstadoIndexacion;
import co.medtender.api.domain.MotivoPurga;
import co.medtender.api.domain.Permiso;
import co.medtender.api.domain.TipoDocumento;
import co.medtender.api.expediente.AutorizacionExpediente;
import co.medtender.api.ingesta.DocumentoDtos.ActaPurgaOut;
import co.medtender.api.ingesta.DocumentoDtos.DocumentoDetalleOut;
import co.medtender.api.ingesta.DocumentoDtos.DocumentoOut;
import co.medtender.api.limites.Limitador;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.Part;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.task.TaskRejectedException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Ingesta efimera de PDFs (Pasos 3, 4 y 9 del flujo obligatorio). */
@RestController
@RequestMapping("/api/v1/expedientes/{expedienteId}/documentos")
public class DocumentoController {

    private static final Logger log = LoggerFactory.getLogger(DocumentoController.class);
    private static final String CAMPO_ARCHIVO = "archivo";
    private static final long HOLGURA_MULTIPART = 64 * 1024; // cabeceras y campos de texto del multipart

    private final AutorizacionExpediente autorizacion;
    private final DocumentoRepository documentos;
    private final ActaPurgaRepository actas;
    private final AlmacenEfimero almacen;
    private final InspectorPdf inspector;
    private final PurgaService purga;
    private final ValidadorAsincrono validador;
    private final Limitador limitador;
    private final AuditoriaService auditoria;
    private final IngestaProperties ingesta;
    private final MedtenderProperties props;

    public DocumentoController(AutorizacionExpediente autorizacion, DocumentoRepository documentos,
                               ActaPurgaRepository actas, AlmacenEfimero almacen, InspectorPdf inspector,
                               PurgaService purga, ValidadorAsincrono validador, Limitador limitador,
                               AuditoriaService auditoria, IngestaProperties ingesta, MedtenderProperties props) {
        this.autorizacion = autorizacion;
        this.documentos = documentos;
        this.actas = actas;
        this.almacen = almacen;
        this.inspector = inspector;
        this.purga = purga;
        this.validador = validador;
        this.limitador = limitador;
        this.auditoria = auditoria;
        this.ingesta = ingesta;
        this.props = props;
    }

    private record Metadatos(TipoDocumento tipo, int numeroAdenda) {}

    /**
     * Recibe el PDF y responde 202 con estado VALIDANDO. El antivirus y la validacion estructural
     * (contrasena, PDF corrupto) continuan en segundo plano; el resultado se consulta con
     * GET .../documentos/{id}. Un rechazo deja el documento en ERROR_PURGADO con su motivo y su acta.
     */
    @org.springframework.beans.factory.annotation.Autowired
    private co.medtender.api.privacidad.ConsentimientoService consentimiento;

    @PostMapping
    public ResponseEntity<DocumentoOut> subir(@PathVariable UUID expedienteId, HttpServletRequest req,
                                              @AuthenticationPrincipal UsuarioActual user) {
        var a = autorizacion.obtener(user, expedienteId, Permiso.EDITOR);
        consentimiento.exigir(user);
        if (a.expediente().getEstado() != EstadoExpediente.ABIERTO) {
            throw new ApiException(HttpStatus.CONFLICT, "El expediente no está abierto");
        }
        if (documentos.hayReindexacionActiva(expedienteId)) {
            throw new ApiException(HttpStatus.CONFLICT,
                    "El expediente se está re-vectorizando con otro modelo; intente al terminar");
        }
        // Antes de aceptar bytes: cada subida cuesta disco, antivirus y llamadas de embeddings.
        limitador.exigir("subida_usuario", user.id().toString(), props.rateLimit().subidaUsuarioHora(), 3600);
        verificarCabeceras(req);

        // --- recepcion: Tomcat deja el archivo en el directorio efimero (nunca en memoria ni en /tmp) ---
        try {
            Part parte = leerParte(req);
            return procesarSubida(expedienteId, req, user, a, parte);
        } finally {
            // Con umbral 0 Tomcat guarda en disco TODAS las partes (tambien los campos de texto).
            // Que no esperen al reciclado de la peticion: se borran ya (lo ya movido no se toca).
            borrarTemporales(req);
        }
    }

    private void borrarTemporales(HttpServletRequest req) {
        try {
            for (Part p : req.getParts()) {
                p.delete();
            }
        } catch (IOException | ServletException | IllegalStateException e) {
            log.warn("No se pudieron borrar los temporales de la subida: {}", e.toString());
        }
    }

    private ResponseEntity<DocumentoOut> procesarSubida(UUID expedienteId, HttpServletRequest req, UsuarioActual user,
                                                        AutorizacionExpediente.Autorizado a, Part parte) {
        Metadatos meta = leerMetadatos(req);

        UUID documentoId = UUID.randomUUID();
        Path parcial = almacen.rutaParcial(documentoId);
        boolean insertado = false;
        try {
            long t0 = System.nanoTime();
            try {
                parte.write(parcial.getFileName().toString()); // renombra el temporal de Tomcat a {id}.part
            } catch (IOException e) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "No se pudo recibir el archivo");
            }
            Recibido recibido = resumir(parcial, nombreBase(parte.getSubmittedFileName()));
            log.info("Recepcion documento={} {} MB en {} s", documentoId,
                    String.format("%.1f", recibido.tamano() / 1e6), String.format("%.1f", (System.nanoTime() - t0) / 1e9));

            var duplicados = documentos.duplicados(user.tenantId(), expedienteId, recibido.sha256());
            if (!duplicados.isEmpty()) {
                Map<String, Object> detalle = new LinkedHashMap<>();
                detalle.put("msg", "Este documento ya fue cargado en el expediente");
                detalle.put("documento_id", duplicados.get(0).toString());
                throw new ApiException(HttpStatus.CONFLICT, detalle);
            }

            Documento d = new Documento(documentoId, user.tenantId(), expedienteId, recibido.nombre(), meta.tipo(),
                    meta.numeroAdenda(), recibido.sha256(), recibido.tamano(), a.expediente().getEmbeddingModelActivo());
            d = documentos.saveAndFlush(d);
            insertado = true;
            auditoria.auditar(Accion.DOCUMENTO_SUBIDO, user, "documento", documentoId, Map.of(
                    "expediente", expedienteId.toString(), "tipo", meta.tipo().name(),
                    "sha256", recibido.sha256(), "bytes", recibido.tamano()));
            // El formato lo decide el contenido. Si no es nada soportado se guarda como .pdf solo para que la
            // purga de abajo lo encuentre; el rechazo es inmediato.
            var formatoDetectado = inspector.detectarFormato(recibido.cabecera());
            d.setFormato(formatoDetectado.orElse(co.medtender.api.domain.FormatoDocumento.PDF));
            Files.move(parcial, almacen.rutaDocumento(documentoId, d.getFormato()), StandardCopyOption.ATOMIC_MOVE);

            d.transicionar(EstadoIndexacion.VALIDANDO);
            d = documentos.saveAndFlush(d);

            // La firma binaria se comprueba aqui (instantaneo, no parsea nada) para dar respuesta
            // inmediata; antivirus y estructura van en segundo plano.
            if (formatoDetectado.isEmpty()) {
                var rechazado = purga.rechazar(documentoId, MotivoPurga.ERROR_VALIDACION,
                        "El archivo no es un PDF ni una imagen compatible (JPG, PNG o HEIC)").orElse(d);
                Map<String, Object> extra = new LinkedHashMap<>();
                extra.put("documento", DocumentoOut.de(rechazado, ingesta.ocrVersionActual()));
                throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, rechazado.getMotivoError(), extra);
            }

            try {
                validador.validarYEncolar(documentoId);
            } catch (TaskRejectedException e) {
                purga.fallarYPurgar(documentoId, MotivoPurga.ERROR_PROCESAMIENTO,
                        "El servidor está saturado; vuelva a cargar el PDF en unos minutos");
                throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE,
                        "El servidor está saturado; intente de nuevo en unos minutos");
            }
            return ResponseEntity.accepted().body(DocumentoOut.de(d, ingesta.ocrVersionActual()));
        } catch (ApiException e) {
            if (!insertado) {
                almacen.borrarTodo(documentoId);
            }
            throw e;
        } catch (Throwable t) {
            // Garantia de borrado: ningun camino de error deja el PDF en disco.
            if (insertado) {
                purga.fallarYPurgar(documentoId, MotivoPurga.ERROR_PROCESAMIENTO,
                        "Error interno en la ingesta: " + t.getClass().getSimpleName());
            } else {
                almacen.borrarTodo(documentoId);
            }
            if (t instanceof RuntimeException re) {
                throw re;
            }
            throw new IllegalStateException(t);
        }
    }

    @GetMapping
    public List<DocumentoOut> listar(@PathVariable UUID expedienteId, @AuthenticationPrincipal UsuarioActual user) {
        autorizacion.obtener(user, expedienteId, Permiso.LECTOR);
        return documentos.findByTenantIdAndExpedienteIdOrderByUploadedAtDesc(user.tenantId(), expedienteId).stream()
                .map(d -> DocumentoOut.de(d, ingesta.ocrVersionActual())).toList();
    }

    /** Estado del pipeline (para la barra de progreso) y actas de purga. */
    @GetMapping("/{documentoId}")
    public DocumentoDetalleOut obtener(@PathVariable UUID expedienteId, @PathVariable UUID documentoId,
                                       @AuthenticationPrincipal UsuarioActual user) {
        Documento d = documentoAutorizado(user, expedienteId, documentoId, Permiso.LECTOR);
        var detalle = actas.findByDocumentoIdAndTenantIdOrderByPurgedAt(d.getId(), user.tenantId()).stream()
                .map(ActaPurgaOut::de).toList();
        return new DocumentoDetalleOut(DocumentoOut.de(d, ingesta.ocrVersionActual()), detalle);
    }

    /** Elimina el documento y sus fragmentos. El acta de purga se conserva. */
    @DeleteMapping("/{documentoId}")
    public ResponseEntity<Void> eliminar(@PathVariable UUID expedienteId, @PathVariable UUID documentoId,
                                         @AuthenticationPrincipal UsuarioActual user) {
        Documento d = documentoAutorizado(user, expedienteId, documentoId, Permiso.EDITOR);
        purga.eliminar(d, user.email());
        auditoria.auditar(Accion.DOCUMENTO_ELIMINADO, user, "documento", documentoId,
                Map.of("expediente", expedienteId.toString(), "sha256", d.getSha256Original()));
        return ResponseEntity.noContent().build();
    }

    private Documento documentoAutorizado(UsuarioActual user, UUID expedienteId, UUID documentoId, Permiso minimo) {
        autorizacion.obtener(user, expedienteId, minimo);
        return documentos.findByIdAndExpedienteIdAndTenantId(documentoId, expedienteId, user.tenantId())
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "Documento no encontrado"));
    }

    // ---------- recepcion ----------

    private void verificarCabeceras(HttpServletRequest req) {
        String tipo = req.getContentType();
        if (tipo == null || !tipo.toLowerCase().startsWith("multipart/form-data")) {
            throw new ApiException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "Se espera multipart/form-data");
        }
        long longitud = req.getContentLengthLong();
        if (longitud > ingesta.maxUploadBytes() + HOLGURA_MULTIPART) {
            throw new ApiException(HttpStatus.PAYLOAD_TOO_LARGE, textoMaximo());
        }
    }

    private String textoMaximo() {
        return "El archivo supera el máximo de " + ingesta.maxUploadMb() + " MB";
    }

    private Part leerParte(HttpServletRequest req) {
        Part parte;
        try {
            parte = req.getPart(CAMPO_ARCHIVO);
        } catch (IllegalStateException e) {
            // Tomcat lo lanza al superar el tamano maximo del archivo o de la peticion.
            throw new ApiException(HttpStatus.PAYLOAD_TOO_LARGE, textoMaximo());
        } catch (IOException | ServletException e) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "Multipart mal formado");
        }
        if (parte == null || parte.getSubmittedFileName() == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "Falta el archivo 'archivo'");
        }
        if (parte.getSize() == 0) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "El archivo está vacío");
        }
        return parte;
    }

    private Metadatos leerMetadatos(HttpServletRequest req) {
        String tipoTexto = req.getParameter("tipo_documento");
        TipoDocumento tipo;
        try {
            tipo = TipoDocumento.valueOf(tipoTexto == null ? "" : tipoTexto);
        } catch (IllegalArgumentException e) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "tipo_documento: debe ser uno de " + java.util.Arrays.toString(TipoDocumento.values()));
        }
        int adenda;
        try {
            String texto = req.getParameter("numero_adenda");
            adenda = texto == null || texto.isBlank() ? 0 : Integer.parseInt(texto.trim());
        } catch (NumberFormatException e) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "numero_adenda: debe ser un entero");
        }
        if (adenda < 0 || adenda > 999) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "numero_adenda: debe estar entre 0 y 999");
        }
        if (tipo == TipoDocumento.ADENDA && adenda < 1) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "Una ADENDA requiere numero_adenda >= 1");
        }
        if (tipo != TipoDocumento.ADENDA && adenda != 0) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "numero_adenda solo aplica a documentos tipo ADENDA");
        }
        return new Metadatos(tipo, adenda);
    }

    private record Recibido(String sha256, long tamano, byte[] cabecera, String nombre) {}

    /** Una sola lectura del archivo: SHA-256, tamano y los primeros bytes para la firma. */
    private static Recibido resumir(Path ruta, String nombre) {
        try (InputStream in = Files.newInputStream(ruta)) {
            MessageDigest sha = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[1024 * 1024];
            byte[] cabecera = new byte[0];
            long total = 0;
            int n;
            while ((n = in.read(buffer)) > 0) {
                if (cabecera.length == 0) {
                    cabecera = java.util.Arrays.copyOf(buffer, Math.min(n, InspectorPdf.VENTANA_CABECERA));
                }
                sha.update(buffer, 0, n);
                total += n;
            }
            return new Recibido(HexFormat.of().formatHex(sha.digest()), total, cabecera, nombre);
        } catch (IOException | NoSuchAlgorithmException e) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "No se pudo leer el archivo recibido");
        }
    }

    /** Solo se conserva el nombre base como metadato; nunca se usa como ruta. */
    private static String nombreBase(String enviado) {
        String limpio = enviado == null ? "" : enviado.replace('\\', '/');
        limpio = limpio.substring(limpio.lastIndexOf('/') + 1);
        if (limpio.isBlank()) {
            return "documento.pdf";
        }
        return limpio.length() > 255 ? limpio.substring(0, 255) : limpio;
    }
}

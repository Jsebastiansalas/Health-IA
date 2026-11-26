package co.medtender.api.recordatorios;

import co.medtender.api.domain.Recordatorio;
import co.medtender.api.domain.Recordatorio.Estado;
import co.medtender.api.domain.RecordatorioRepository;
import co.medtender.api.security.UsuarioActual;
import co.medtender.api.web.ApiException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDate;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Recordatorios de controles: guarda las propuestas del agente (sin repetir), las lista y aplica lo que decide
 * la persona. Un recordatorio solo es visible para quien lo creó.
 */
@Service
public class RecordatorioService {

    private final RecordatorioRepository repo;
    private final ObjectMapper json;

    public RecordatorioService(RecordatorioRepository repo, ObjectMapper json) {
        this.repo = repo;
        this.json = json;
    }

    public record RecordatorioOut(UUID id, UUID expedienteId, String texto, String fechaTexto, LocalDate fechaDocumento,
                                  LocalDate fechaPropuesta, LocalDate fecha, Estado estado, Map<String, Object> cita,
                                  boolean avisado) {
        static RecordatorioOut de(Recordatorio r) {
            return new RecordatorioOut(r.getId(), r.getExpedienteId(), r.getTexto(), r.getFechaTexto(), r.getFechaDocumento(),
                    r.getFechaPropuesta(), r.getFecha(), r.getEstado(), r.getCita(), r.getAvisoEnviadoAt() != null);
        }
    }

    static String clave(String texto, String documentoId, String fechaTexto) {
        try {
            String base = String.join("|", texto.strip().toLowerCase(), documentoId == null ? "" : documentoId,
                    fechaTexto == null ? "" : fechaTexto.strip().toLowerCase());
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(base.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    private static LocalDate fecha(JsonNode n) {
        return n == null || n.isNull() || n.asString("").isBlank() ? null : LocalDate.parse(n.asString(""));
    }

    private static String recortar(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max);
    }

    /** Guarda las propuestas nuevas del agente. Devuelve cuántas eran nuevas. */
    @Transactional
    @SuppressWarnings("unchecked")
    public int guardarPropuestas(UsuarioActual u, UUID expedienteId, JsonNode propuestas) {
        int nuevas = 0;
        for (JsonNode p : propuestas) {
            String texto = p.path("texto").asString("").strip();
            if (texto.isEmpty() || !p.hasNonNull("cita")) continue;
            String fechaTexto = p.path("fechaTexto").asString("");
            String clave = clave(texto, p.path("cita").path("documentoId").asString(null), fechaTexto);
            if (repo.existsByUsuarioIdAndExpedienteIdAndClave(u.id(), expedienteId, clave)) continue;
            Map<String, Object> cita = json.convertValue(p.get("cita"), Map.class);
            repo.save(new Recordatorio(u.tenantId(), u.id(), expedienteId, recortar(texto, 300), recortar(fechaTexto, 120),
                    fecha(p.get("fechaDocumento")), fecha(p.get("fechaPropuesta")), cita, clave));
            nuevas++;
        }
        return nuevas;
    }

    @Transactional(readOnly = true)
    public List<RecordatorioOut> listar(UsuarioActual u, UUID expedienteId) {
        return repo.vigentesDe(u.id()).stream()
                .filter(r -> expedienteId == null || r.getExpedienteId().equals(expedienteId))
                .map(RecordatorioOut::de)
                .toList();
    }

    @Transactional(readOnly = true)
    public Recordatorio obtener(UsuarioActual u, UUID id) {
        return repo.findByIdAndUsuarioId(id, u.id())
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "Recordatorio no encontrado"));
    }

    /** Confirmar exige fecha (la que propone el documento o la que ponga la persona). */
    @Transactional
    public RecordatorioOut actualizar(UsuarioActual u, UUID id, Estado estado, LocalDate fecha) {
        Recordatorio r = obtener(u, id);
        LocalDate efectiva = fecha != null ? fecha : r.getFecha() != null ? r.getFecha() : r.getFechaPropuesta();
        if (estado == Estado.CONFIRMADO && efectiva == null) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "Pon una fecha para confirmar el recordatorio",
                    Map.of("codigo", "fecha_requerida"));
        }
        r.actualizar(estado, estado == Estado.CONFIRMADO ? efectiva : fecha);
        return RecordatorioOut.de(repo.save(r));
    }
}

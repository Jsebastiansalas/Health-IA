package co.medtender.api.privacidad;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.util.HtmlUtils;

/**
 * «Descargar mis datos»: un ZIP con lo que hay de una cuenta personal, en JSON y en una página legible. Se arma
 * en memoria cuando se pide y no se guarda en ningún lado.
 *
 * <p>Las columnas se nombran una a una a propósito: así la huella de la contraseña, el secreto de los dos pasos,
 * las sesiones y los vectores no pueden colarse porque alguien añada una columna.
 */
@Service
public class ExportacionService {

    private static final DateTimeFormatter FECHA =
            DateTimeFormatter.ofPattern("d/M/yyyy HH:mm").withZone(ZoneId.of("America/Bogota"));

    private static final String LEEME = """
            Tus datos en MedTender

            - resumen.html: la versión para leer. Ábrela con tu navegador.
            - datos.json: lo mismo en un formato que otro programa puede leer.

            Incluye tu cuenta, tus consentimientos, tus expedientes, el texto que se leyó de tus documentos con su
            página, tus preguntas y las respuestas (también explicaciones, líneas de tiempo y preparaciones de cita
            que se guardaron), tus recordatorios, las constancias de borrado de los archivos y el registro de accesos.

            No incluye:
            - Los archivos originales: se eliminan del servidor después de leerlos.
            - Tu contraseña, los códigos de seguridad ni los datos internos que usa la búsqueda.

            Este archivo contiene información de salud. Guárdalo en un lugar seguro y borra las copias que no necesites.
            """;

    public record Exportacion(byte[] zip, Map<String, Object> conteos) {}

    private final JdbcTemplate jdbc;
    private final ObjectMapper json;

    private final CifradoDatos cifrado;

    public ExportacionService(JdbcTemplate jdbc, ObjectMapper json, CifradoDatos cifrado) {
        this.cifrado = cifrado;
        this.jdbc = jdbc;
        this.json = json;
    }

    /** Corre en el contexto del tenant: RLS limita las filas y además cada consulta filtra por él. */
    public Exportacion exportar(UUID tenantId, UUID usuarioId) {
        ObjectNode datos = json.createObjectNode();
        datos.put("generado_at", OffsetDateTime.now().toString());
        datos.set("cuenta", jdbc.queryForObject("""
                select email, nombre_completo, created_at, totp_activo from usuarios where id = ? and tenant_id = ?""",
                (rs, n) -> objeto(rs, "correo", "email", "nombre", "nombre_completo", "creada_at", "created_at",
                        "verificacion_en_dos_pasos", "totp_activo"),
                usuarioId, tenantId));
        datos.set("consentimientos", lista("""
                select version, aceptado_at from consentimientos where tenant_id = ? order by aceptado_at""",
                new String[] {"version", "version", "aceptado_at", "aceptado_at"}, tenantId));

        int[] conteos = new int[3]; // expedientes, documentos, consultas
        ArrayNode expedientes = datos.putArray("expedientes");
        jdbc.query("select id, codigo_expediente, titulo, created_at from expedientes where tenant_id = ? order by created_at",
                rs -> {
                    ObjectNode e = objeto(rs, "codigo", "codigo_expediente", "titulo", "titulo", "creado_at", "created_at");
                    expedientes.add(e);
                    UUID id = rs.getObject("id", UUID.class);
                    ArrayNode documentos = e.putArray("documentos");
                    documentos(tenantId, id, documentos);
                    ArrayNode consultas = consultas(tenantId, id);
                    e.set("consultas", consultas);
                    e.set("constancias_de_borrado", lista("""
                            select a.sha256_original, a.motivo, a.purged_at from actas_purga a
                            join documentos d on d.id = a.documento_id
                            where a.tenant_id = ? and d.expediente_id = ? order by a.purged_at""",
                            new String[] {"sha256_original", "sha256_original", "motivo", "motivo", "fecha", "purged_at"},
                            tenantId, id));
                    e.set("compartido_con", lista("""
                            select correo_invitado, permiso, estado, created_at, aceptada_at, ultimo_acceso_at, revocada_at
                            from comparticiones where tenant_id = ? and expediente_id = ? order by created_at""",
                            new String[] {"correo", "correo_invitado", "permiso", "permiso", "estado", "estado",
                                    "invitado_at", "created_at", "aceptada_at", "aceptada_at",
                                    "ultimo_acceso_at", "ultimo_acceso_at", "revocada_at", "revocada_at"},
                            tenantId, id));
                    conteos[0]++;
                    conteos[1] += documentos.size();
                    conteos[2] += consultas.size();
                }, tenantId);

        datos.set("recordatorios", lista("""
                select r.texto, r.fecha_texto, r.fecha, r.estado, r.created_at,
                       coalesce(e.titulo, 'Expediente que comparten contigo') as titulo from recordatorios r
                left join expedientes e on e.id = r.expediente_id
                where r.tenant_id = ? and r.usuario_id = ? order by r.created_at""",
                new String[] {"texto", "texto", "fecha_en_el_documento", "fecha_texto", "fecha", "fecha", "estado", "estado",
                        "creado_at", "created_at", "expediente", "titulo"},
                tenantId, usuarioId));
        datos.set("accesos", lista("""
                select created_at, accion, resultado, ip from auditoria
                where tenant_id = ? and usuario_id = ? order by created_at""",
                new String[] {"fecha", "created_at", "accion", "accion", "resultado", "resultado", "ip", "ip"},
                tenantId, usuarioId));

        var zip = new ByteArrayOutputStream();
        try (var salida = new ZipOutputStream(zip, StandardCharsets.UTF_8)) {
            escribir(salida, "LEEME.txt", LEEME);
            escribir(salida, "datos.json", json.writerWithDefaultPrettyPrinter().writeValueAsString(datos));
            escribir(salida, "resumen.html", html(datos));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        return new Exportacion(zip.toByteArray(),
                Map.of("expedientes", conteos[0], "documentos", conteos[1], "consultas", conteos[2]));
    }

    private void documentos(UUID tenantId, UUID expedienteId, ArrayNode salida) {
        jdbc.query("""
                select id, nombre_archivo_original, tipo_documento, total_paginas, sha256_original, uploaded_at
                from documentos where tenant_id = ? and expediente_id = ? order by uploaded_at""",
                rs -> {
                    ObjectNode d = objeto(rs, "nombre", "nombre_archivo_original", "tipo", "tipo_documento",
                            "paginas", "total_paginas", "sha256_original", "sha256_original", "subido_at", "uploaded_at");
                    d.set("fragmentos", lista("""
                            select pagina_inicio, pagina_fin, seccion, contenido_texto from fragmentos
                            where tenant_id = ? and documento_id = ? order by orden""",
                            new String[] {"pagina_inicio", "pagina_inicio", "pagina_fin", "pagina_fin", "seccion", "seccion",
                                    "texto", "contenido_texto"},
                            tenantId, rs.getObject("id", UUID.class)));
                    leidoParaLaLinea(tenantId, rs.getObject("id", UUID.class), d);
                    salida.add(d);
                }, tenantId, expedienteId);
    }

    /** Lo que la IA propuso al leer el documento para la línea de tiempo: también es un dato de la persona. */
    private void leidoParaLaLinea(UUID tenantId, UUID documentoId, ObjectNode documento) {
        jdbc.query("""
                select created_at, datos::text as datos from extracciones_linea
                where tenant_id = ? and documento_id = ?""",
                rs -> {
                    ObjectNode leido = objeto(rs, "fecha", "created_at");
                    leido.put("aviso", "Propuestas de la IA sin comprobar; la línea de tiempo solo muestra lo que "
                            + "coincide con el texto del documento.");
                    try {
                        leido.set("datos", cifrado.respuesta(json.readTree(rs.getString("datos"))));
                    } catch (JacksonException e) {
                        throw new IllegalStateException("Extracción guardada ilegible", e);
                    }
                    documento.set("leido_para_la_linea_de_tiempo", leido);
                }, tenantId, documentoId);
    }

    private ArrayNode consultas(UUID tenantId, UUID expedienteId) {
        ArrayNode salida = json.createArrayNode();
        jdbc.query("""
                select created_at, pregunta, respuesta::text as respuesta from consultas
                where tenant_id = ? and expediente_id = ? order by created_at""",
                rs -> {
                    ObjectNode c = objeto(rs, "fecha", "created_at");
                    c.put("pregunta", cifrado.texto(rs.getString("pregunta")));
                    try {
                        c.set("respuesta", cifrado.respuesta(json.readTree(rs.getString("respuesta"))));
                    } catch (JacksonException e) {
                        throw new IllegalStateException("Respuesta guardada ilegible", e);
                    }
                    salida.add(c);
                }, tenantId, expedienteId);
        return salida;
    }

    private ArrayNode lista(String sql, String[] pares, Object... args) {
        ArrayNode salida = json.createArrayNode();
        jdbc.query(sql, rs -> {
            salida.add(objeto(rs, pares));
        }, args);
        return salida;
    }

    /** `pares` alterna el nombre en el JSON y la columna. */
    private ObjectNode objeto(ResultSet rs, String... pares) throws SQLException {
        ObjectNode o = json.createObjectNode();
        for (int i = 0; i < pares.length; i += 2) {
            Object v = rs.getObject(pares[i + 1]);
            switch (v) {
                case null -> o.putNull(pares[i]);
                case Integer n -> o.put(pares[i], n);
                case Boolean b -> o.put(pares[i], b);
                case java.sql.Timestamp t -> o.put(pares[i], t.toInstant().toString());
                default -> o.put(pares[i], v.toString().strip());
            }
        }
        return o;
    }

    private static void escribir(ZipOutputStream zip, String nombre, String contenido) throws IOException {
        zip.putNextEntry(new ZipEntry(nombre));
        zip.write(contenido.getBytes(StandardCharsets.UTF_8));
        zip.closeEntry();
    }

    // ---------- versión legible: todo texto que viene de la persona o de sus documentos se escapa ----------

    private static String e(String s) {
        return HtmlUtils.htmlEscape(s, "UTF-8");
    }

    private static String fecha(JsonNode n) {
        return n.isNull() || n.isMissingNode() ? "" : FECHA.format(java.time.Instant.parse(n.asString("")));
    }

    private static String html(JsonNode datos) {
        var h = new StringBuilder("""
                <!doctype html><html lang="es"><head><meta charset="utf-8">
                <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
                <title>Mis datos en MedTender</title>
                <style>body{font-family:system-ui,sans-serif;max-width:48rem;margin:2rem auto;padding:0 1rem;line-height:1.5}
                pre{white-space:pre-wrap;background:#f4f4f2;padding:.75rem;border-radius:6px}h2{margin-top:2.5rem}
                dt{font-weight:600}</style></head><body><h1>Mis datos en MedTender</h1>
                """);
        JsonNode cuenta = datos.get("cuenta");
        h.append("<p>").append(e(cuenta.get("nombre").asString(""))).append(" · ").append(e(cuenta.get("correo").asString("")))
                .append("<br>Cuenta creada el ").append(fecha(cuenta.get("creada_at"))).append("</p>");

        h.append("<h2>Consentimientos aceptados</h2><ul>");
        datos.get("consentimientos").forEach(c -> h.append("<li>").append(e(c.get("version").asString(""))).append(" · ")
                .append(fecha(c.get("aceptado_at"))).append("</li>"));
        h.append("</ul>");

        for (JsonNode exp : datos.get("expedientes")) {
            h.append("<h2>").append(e(exp.get("titulo").asString(""))).append("</h2>");
            for (JsonNode d : exp.get("documentos")) {
                h.append("<h3>").append(e(d.get("nombre").asString(""))).append("</h3>");
                for (JsonNode f : d.get("fragmentos")) {
                    int desde = f.get("pagina_inicio").asInt(0);
                    int hasta = f.get("pagina_fin").asInt(0);
                    h.append("<p><small>").append(desde == hasta ? "página " + desde : "páginas " + desde + "–" + hasta)
                            .append("</small></p><pre>").append(e(f.get("texto").asString(""))).append("</pre>");
                }
            }
            if (!exp.get("consultas").isEmpty()) {
                h.append("<h3>Preguntas y respuestas guardadas</h3>");
                for (JsonNode c : exp.get("consultas")) {
                    h.append("<p><strong>").append(e(c.get("pregunta").asString(""))).append("</strong> <small>")
                            .append(fecha(c.get("fecha"))).append("</small></p>");
                    valor(h, c.get("respuesta"));
                }
            }
        }

        if (!datos.get("recordatorios").isEmpty()) {
            h.append("<h2>Recordatorios</h2><ul>");
            datos.get("recordatorios").forEach(r -> h.append("<li>").append(e(r.get("texto").asString("")))
                    .append(r.get("fecha").isNull() ? "" : " · " + e(r.get("fecha").asString("")))
                    .append(" (").append(e(r.get("estado").asString(""))).append(")</li>"));
            h.append("</ul>");
        }

        h.append("<h2>Registro de accesos</h2><ul>");
        datos.get("accesos").forEach(a -> h.append("<li>").append(fecha(a.get("fecha"))).append(" · ")
                .append(e(a.get("accion").asString(""))).append(" · ").append(e(a.get("resultado").asString("")))
                .append(" · ").append(e(a.get("ip").asString(""))).append("</li>"));
        return h.append("</ul></body></html>").toString();
    }

    /** Muestra cualquier respuesta guardada, sea cual sea su forma, como listas anidadas. */
    private static void valor(StringBuilder h, JsonNode v) {
        if (v.isObject()) {
            var campos = new LinkedHashMap<String, JsonNode>();
            v.properties().forEach(c -> campos.put(c.getKey(), c.getValue()));
            h.append("<dl>");
            campos.forEach((nombre, hijo) -> {
                if (!vacio(hijo)) {
                    h.append("<dt>").append(e(nombre)).append("</dt><dd>");
                    valor(h, hijo);
                    h.append("</dd>");
                }
            });
            h.append("</dl>");
        } else if (v.isArray()) {
            h.append("<ul>");
            v.forEach(hijo -> {
                h.append("<li>");
                valor(h, hijo);
                h.append("</li>");
            });
            h.append("</ul>");
        } else {
            h.append(e(v.asString("")));
        }
    }

    private static boolean vacio(JsonNode v) {
        return v.isNull() || (v.isContainer() && v.isEmpty()) || (v.isString() && v.asString("").isBlank());
    }
}

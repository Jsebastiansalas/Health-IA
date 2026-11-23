package co.medtender.api;

import co.medtender.api.limites.AlmacenLimites;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Stream;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

/** Ingesta de extremo a extremo sobre HTTP real (Tomcat + multipart), clamd y agente simulados. */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class IngestaIT {

    private static final String PASS = "Clave-Segura-123";

    @DynamicPropertySource
    static void propiedades(DynamicPropertyRegistry r) {
        Infra.registrar(r);
    }

    @LocalServerPort int puerto;
    @Autowired ObjectMapper json;
    @Autowired AlmacenLimites limites;
    /** Propietario de la base: ve todos los tenants (la aplicacion usa `medtender_app` con RLS). */
    private final org.springframework.jdbc.core.JdbcTemplate jdbc = Infra.admin();

    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();
    private String token;
    private String expediente;

    record Respuesta(int estado, JsonNode cuerpo) {}

    @BeforeEach
    void preparar() throws Exception {
        jdbc.execute("TRUNCATE auditoria, actas_purga, documentos, expedientes, usuarios, tenants CASCADE");
        limites.reiniciar();
        Infra.AGENTE.reiniciar();
        Infra.CLAMD.disponible(true);
        try (Stream<Path> archivos = Files.list(Infra.EFIMERO)) {
            archivos.forEach(p -> p.toFile().delete());
        }
        Respuesta r = enviarJson("POST", "/api/v1/auth/registro-tenant", null, Map.of("tenant_nombre", "Hospital X",
                "nit", "NIT-" + UUID.randomUUID(), "admin_email", "admin-" + UUID.randomUUID() + "@x.co",
                "admin_password", PASS, "admin_nombre", "Admin"));
        assertThat(r.estado()).isEqualTo(201);
        token = r.cuerpo().get("access_token").asText();
        expediente = enviarJson("POST", "/api/v1/expedientes", token, Map.of("codigo_expediente", "LIC-1",
                "titulo", "Licitación", "tipo_expediente", "LICITACION_MEDICAMENTOS")).cuerpo().get("id").asText();
    }

    // ---------- utilidades HTTP ----------

    private Respuesta enviarJson(String metodo, String ruta, String tk, Object cuerpo) throws Exception {
        var b = HttpRequest.newBuilder(URI.create("http://localhost:" + puerto + ruta))
                .header("Content-Type", "application/json");
        if (tk != null) b.header("Authorization", "Bearer " + tk);
        b.method(metodo, cuerpo == null ? HttpRequest.BodyPublishers.noBody()
                : HttpRequest.BodyPublishers.ofString(json.writeValueAsString(cuerpo)));
        return leer(http.send(b.build(), HttpResponse.BodyHandlers.ofString()));
    }

    private Respuesta get(String ruta, String tk) throws Exception {
        var b = HttpRequest.newBuilder(URI.create("http://localhost:" + puerto + ruta)).GET();
        if (tk != null) b.header("Authorization", "Bearer " + tk);
        return leer(http.send(b.build(), HttpResponse.BodyHandlers.ofString()));
    }

    private Respuesta leer(HttpResponse<String> r) throws IOException {
        return new Respuesta(r.statusCode(), r.body().isBlank() ? json.createObjectNode() : json.readTree(r.body()));
    }

    private Respuesta subir(String exp, String tk, byte[] archivo, String nombre, Map<String, String> campos) throws Exception {
        String limite = "----medtender" + UUID.randomUUID();
        ByteArrayOutputStream cuerpo = new ByteArrayOutputStream();
        for (var c : campos.entrySet()) {
            cuerpo.write(("--" + limite + "\r\nContent-Disposition: form-data; name=\"" + c.getKey() + "\"\r\n\r\n"
                    + c.getValue() + "\r\n").getBytes(StandardCharsets.UTF_8));
        }
        if (archivo != null) {
            cuerpo.write(("--" + limite + "\r\nContent-Disposition: form-data; name=\"archivo\"; filename=\"" + nombre
                    + "\"\r\nContent-Type: application/pdf\r\n\r\n").getBytes(StandardCharsets.UTF_8));
            cuerpo.write(archivo);
            cuerpo.write("\r\n".getBytes(StandardCharsets.UTF_8));
        }
        cuerpo.write(("--" + limite + "--\r\n").getBytes(StandardCharsets.UTF_8));
        var b = HttpRequest.newBuilder(URI.create("http://localhost:" + puerto + "/api/v1/expedientes/" + exp + "/documentos"))
                .header("Content-Type", "multipart/form-data; boundary=" + limite)
                .POST(HttpRequest.BodyPublishers.ofByteArray(cuerpo.toByteArray()));
        if (tk != null) b.header("Authorization", "Bearer " + tk);
        return leer(http.send(b.build(), HttpResponse.BodyHandlers.ofString()));
    }

    private Respuesta subirPliego(byte[] archivo) throws Exception {
        return subir(expediente, token, archivo, "pliego.pdf", Map.of("tipo_documento", "PLIEGO"));
    }

    private JsonNode esperarEstadoFinalDeValidacion(String docId) {
        var resultado = new JsonNode[1];
        await().atMost(Duration.ofSeconds(30)).pollInterval(Duration.ofMillis(100)).until(() -> {
            resultado[0] = get("/api/v1/expedientes/" + expediente + "/documentos/" + docId, token).cuerpo();
            String estado = resultado[0].get("estado_indexacion").asText();
            return !estado.equals("RECIBIDO") && !estado.equals("VALIDANDO");
        });
        return resultado[0];
    }

    private JsonNode esperarEstado(String docId, String estadoEsperado) {
        var resultado = new JsonNode[1];
        await().atMost(Duration.ofSeconds(30)).pollInterval(Duration.ofMillis(100)).until(() -> {
            resultado[0] = get("/api/v1/expedientes/" + expediente + "/documentos/" + docId, token).cuerpo();
            return resultado[0].get("estado_indexacion").asText().equals(estadoEsperado);
        });
        return resultado[0];
    }

    private List<String> archivosEfimeros() throws IOException {
        try (Stream<Path> s = Files.list(Infra.EFIMERO)) {
            return s.map(p -> p.getFileName().toString()).toList();
        }
    }

    private static String sha256(byte[] datos) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(datos));
    }

    private int actas(String docId, String motivo) {
        return jdbc.queryForObject("select count(*) from actas_purga where documento_id = ?::uuid and motivo = ?",
                Integer.class, docId, motivo);
    }

    // ---------- camino feliz ----------

    @Test
    void pdfValidoSeValidaYSeEntregaAlAgente() throws Exception {
        byte[] pdf = PdfsDePrueba.valido(3);
        Respuesta r = subirPliego(pdf);

        assertThat(r.estado()).isEqualTo(202);
        assertThat(r.cuerpo().get("estado_indexacion").asText()).isEqualTo("VALIDANDO");
        assertThat(r.cuerpo().get("sha256_original").asText()).isEqualTo(sha256(pdf));
        assertThat(r.cuerpo().get("tamano_bytes").asLong()).isEqualTo(pdf.length);
        assertThat(r.cuerpo().get("nombre_archivo_original").asText()).isEqualTo("pliego.pdf");
        String docId = r.cuerpo().get("id").asText();

        JsonNode d = esperarEstadoFinalDeValidacion(docId);
        assertThat(d.get("estado_indexacion").asText()).isEqualTo("EN_COLA");
        assertThat(d.get("total_paginas").asInt()).isEqualTo(3);
        assertThat(d.get("progreso").asInt()).isEqualTo(15);
        assertThat(d.get("actas_purga")).isEmpty();

        // El agente recibio la entrega con el token interno y exactamente una vez.
        assertThat(Infra.AGENTE.llamadas()).hasSize(1);
        assertThat(Infra.AGENTE.llamadas().get(0).ruta()).isEqualTo("/internal/v1/documentos/" + docId + "/procesar");
        assertThat(Infra.AGENTE.llamadas().get(0).token()).isEqualTo(Infra.AGENTE_TOKEN);

        // El PDF queda en el directorio efimero con el nombre {id}.pdf (lo borrara el agente al indexar).
        assertThat(archivosEfimeros()).containsExactly(docId + ".pdf");
        assertThat(sha256(Files.readAllBytes(Infra.EFIMERO.resolve(docId + ".pdf")))).isEqualTo(sha256(pdf));

        Integer subidos = jdbc.queryForObject("select count(*) from auditoria where accion='DOCUMENTO_SUBIDO'", Integer.class);
        assertThat(subidos).isEqualTo(1);
    }

    @Test
    void pdfConSoloClaveDePropietarioSeAcepta() throws Exception {
        String docId = subirPliego(PdfsDePrueba.soloClaveDePropietario()).cuerpo().get("id").asText();
        assertThat(esperarEstadoFinalDeValidacion(docId).get("estado_indexacion").asText()).isEqualTo("EN_COLA");
    }

    @Test
    void adendaConNumeroYListadoDelExpediente() throws Exception {
        Respuesta r = subir(expediente, token, PdfsDePrueba.valido(1), "adenda1.pdf",
                Map.of("tipo_documento", "ADENDA", "numero_adenda", "2"));
        assertThat(r.estado()).isEqualTo(202);
        assertThat(r.cuerpo().get("tipo_documento").asText()).isEqualTo("ADENDA");
        assertThat(r.cuerpo().get("numero_adenda").asInt()).isEqualTo(2);
        esperarEstadoFinalDeValidacion(r.cuerpo().get("id").asText());

        Respuesta lista = get("/api/v1/expedientes/" + expediente + "/documentos", token);
        assertThat(lista.cuerpo()).hasSize(1);
    }

    // ---------- fotos y escaneos ----------

    private Respuesta subirImagen(byte[] archivo, String nombre) throws Exception {
        return subir(expediente, token, archivo, nombre, Map.of("tipo_documento", "HISTORIA_CLINICA"));
    }

    @Test
    void fotoPngValidaSeAceptaYSeGuardaConSuExtension() throws Exception {
        byte[] foto = PdfsDePrueba.png();
        Respuesta r = subirImagen(foto, "resultado-laboratorio.png"); // el cliente la declara como PDF: no cuenta
        assertThat(r.estado()).isEqualTo(202);
        assertThat(r.cuerpo().get("formato").asText()).isEqualTo("PNG");
        String docId = r.cuerpo().get("id").asText();

        JsonNode d = esperarEstadoFinalDeValidacion(docId);
        assertThat(d.get("estado_indexacion").asText()).isEqualTo("EN_COLA");
        assertThat(d.get("total_paginas").asInt()).isEqualTo(1);
        assertThat(archivosEfimeros()).containsExactly(docId + ".png");
        assertThat(sha256(Files.readAllBytes(Infra.EFIMERO.resolve(docId + ".png")))).isEqualTo(sha256(foto));
        assertThat(Infra.AGENTE.llamadas()).hasSize(1);
    }

    @Test
    void fotoJpgValidaSeAceptaYSeGuardaConSuExtension() throws Exception {
        Respuesta r = subirImagen(PdfsDePrueba.jpg(), "orden-medica.jpg");
        assertThat(r.estado()).isEqualTo(202);
        assertThat(r.cuerpo().get("formato").asText()).isEqualTo("JPG");
        String docId = r.cuerpo().get("id").asText();
        assertThat(esperarEstadoFinalDeValidacion(docId).get("estado_indexacion").asText()).isEqualTo("EN_COLA");
        assertThat(archivosEfimeros()).containsExactly(docId + ".jpg");
    }

    @Test
    void elFormatoSeDecidePorElContenidoNoPorLaExtensionDelNombre() throws Exception {
        Respuesta r = subirImagen(PdfsDePrueba.png(), "parece-un-pdf.pdf");
        assertThat(r.estado()).isEqualTo(202);
        assertThat(r.cuerpo().get("formato").asText()).isEqualTo("PNG");
    }

    @Test
    void unaImagenConFirmaValidaPeroCorruptaSeRechazaEnLaValidacionYSePurga() throws Exception {
        String docId = subirImagen(PdfsDePrueba.pngCorrupto(), "rota.png").cuerpo().get("id").asText();
        JsonNode d = esperarEstadoFinalDeValidacion(docId);
        assertThat(d.get("estado_indexacion").asText()).isEqualTo("ERROR_PURGADO");
        assertThat(d.get("motivo_error").asText()).contains("Imagen corrupta");
        assertThat(archivosEfimeros()).isEmpty();
        assertThat(Infra.AGENTE.llamadas()).isEmpty();
    }

    @Test
    void unFormatoDeImagenNoSoportadoSeRechazaDeInmediato() throws Exception {
        Respuesta r = subirImagen(PdfsDePrueba.gif(), "animacion.gif");
        assertThat(r.estado()).isEqualTo(422);
        assertThat(r.cuerpo().get("detail").asText()).contains("no es un PDF ni una imagen compatible");
        assertThat(archivosEfimeros()).isEmpty();
    }

    @Test
    void laCabeceraHeicSeReconoceAunqueNoSePuedaDecodificarEnJava() {
        var inspector = new co.medtender.api.ingesta.InspectorPdf();
        assertThat(inspector.detectarFormato(PdfsDePrueba.cabeceraHeic()))
                .contains(co.medtender.api.domain.FormatoDocumento.HEIC);
        assertThat(inspector.detectarFormato(PdfsDePrueba.png())).contains(co.medtender.api.domain.FormatoDocumento.PNG);
        assertThat(inspector.detectarFormato(PdfsDePrueba.valido(1))).contains(co.medtender.api.domain.FormatoDocumento.PDF);
        assertThat(inspector.detectarFormato(PdfsDePrueba.noEsPdf())).isEmpty();
    }

    // ---------- rechazos: el archivo nunca queda en disco ----------

    @Test
    void archivoQueNoEsPdfSeRechazaDeInmediatoYSePurga() throws Exception {
        Respuesta r = subirPliego(PdfsDePrueba.noEsPdf());
        assertThat(r.estado()).isEqualTo(422);
        assertThat(r.cuerpo().get("detail").asText()).contains("no es un PDF");
        JsonNode doc = r.cuerpo().get("documento");
        assertThat(doc.get("estado_indexacion").asText()).isEqualTo("ERROR_PURGADO");
        assertThat(doc.get("temp_file_purged").asBoolean()).isTrue();
        assertThat(archivosEfimeros()).isEmpty();
        assertThat(actas(doc.get("id").asText(), "ERROR_VALIDACION")).isEqualTo(1);
        assertThat(Infra.AGENTE.llamadas()).isEmpty();
    }

    @Test
    void pdfConContrasenaDeUsuarioSeRechaza() throws Exception {
        String docId = subirPliego(PdfsDePrueba.conClaveDeUsuario()).cuerpo().get("id").asText();
        JsonNode d = esperarEstadoFinalDeValidacion(docId);
        assertThat(d.get("estado_indexacion").asText()).isEqualTo("ERROR_PURGADO");
        assertThat(d.get("motivo_error").asText()).contains("protegido con contraseña");
        assertThat(d.get("actas_purga")).hasSize(1);
        assertThat(archivosEfimeros()).isEmpty();
        assertThat(Infra.AGENTE.llamadas()).isEmpty();
    }

    @Test
    void pdfCorruptoSeRechaza() throws Exception {
        String docId = subirPliego(PdfsDePrueba.corrupto()).cuerpo().get("id").asText();
        JsonNode d = esperarEstadoFinalDeValidacion(docId);
        assertThat(d.get("estado_indexacion").asText()).isEqualTo("ERROR_PURGADO");
        assertThat(d.get("motivo_error").asText()).contains("corrupto");
        assertThat(archivosEfimeros()).isEmpty();
    }

    @Test
    void archivoConVirusSeRechazaYSePurga() throws Exception {
        String docId = subirPliego(PdfsDePrueba.conEicar()).cuerpo().get("id").asText();
        JsonNode d = esperarEstadoFinalDeValidacion(docId);
        assertThat(d.get("estado_indexacion").asText()).isEqualTo("ERROR_PURGADO");
        assertThat(d.get("motivo_error").asText()).contains("antivirus").contains("Eicar-Test-Signature");
        assertThat(archivosEfimeros()).isEmpty();
        assertThat(actas(docId, "ERROR_VALIDACION")).isEqualTo(1);
        assertThat(Infra.AGENTE.llamadas()).isEmpty();
    }

    @Test
    void sinAntivirusNoSeAceptaNingunArchivo() throws Exception {
        Infra.CLAMD.disponible(false);
        String docId = subirPliego(PdfsDePrueba.valido(1)).cuerpo().get("id").asText();
        JsonNode d = esperarEstadoFinalDeValidacion(docId);
        assertThat(d.get("estado_indexacion").asText()).isEqualTo("ERROR_PURGADO");
        assertThat(d.get("motivo_error").asText()).contains("antivirus no está disponible");
        assertThat(archivosEfimeros()).isEmpty();
    }

    @Test
    void siElAgenteCaeElDocumentoSePurgaTrasLosReintentos() throws Exception {
        Infra.AGENTE.responderCon(503);
        String docId = subirPliego(PdfsDePrueba.valido(1)).cuerpo().get("id").asText();
        JsonNode d = esperarEstado(docId, "ERROR_PURGADO"); // pasa por EN_COLA mientras se reintenta
        assertThat(d.get("estado_indexacion").asText()).isEqualTo("ERROR_PURGADO");
        assertThat(d.get("motivo_error").asText()).contains("servicio de procesamiento no está disponible");
        assertThat(Infra.AGENTE.llamadas()).hasSize(3); // 3 reintentos
        assertThat(archivosEfimeros()).isEmpty();
        assertThat(actas(docId, "ERROR_PROCESAMIENTO")).isEqualTo(1);
    }

    @Test
    void unRechazoDelAgentePorTokenNoSeReintenta() throws Exception {
        Infra.AGENTE.responderCon(401);
        String docId = subirPliego(PdfsDePrueba.valido(1)).cuerpo().get("id").asText();
        JsonNode d = esperarEstado(docId, "ERROR_PURGADO");
        assertThat(d.get("estado_indexacion").asText()).isEqualTo("ERROR_PURGADO");
        assertThat(Infra.AGENTE.llamadas()).hasSize(1);
        assertThat(archivosEfimeros()).isEmpty();
    }

    // ---------- limites y validacion de la peticion ----------

    @Test
    void archivoMasGrandeQueElMaximoDa413SinDejarRastro() throws Exception {
        // Maximo de pruebas: 1 MB. 1,2 MB entra por la holgura del multipart y lo corta el parser...
        Respuesta r = subirPliego(new byte[1_200_000]);
        assertThat(r.estado()).isEqualTo(413);
        // ...y 1,5 MB lo rechaza la cabecera Content-Length antes de leer nada.
        assertThat(subirPliego(new byte[1_500_000]).estado()).isEqualTo(413);
        assertThat(archivosEfimeros()).isEmpty();
        assertThat(jdbc.queryForObject("select count(*) from documentos", Integer.class)).isZero();
    }

    @Test
    void metadatosInvalidosDan422YNoDejanArchivos() throws Exception {
        byte[] pdf = PdfsDePrueba.valido(1);
        assertThat(subir(expediente, token, pdf, "a.pdf", Map.of("tipo_documento", "INVENTADO")).estado()).isEqualTo(422);
        assertThat(subir(expediente, token, pdf, "a.pdf", Map.of("tipo_documento", "ADENDA")).estado()).isEqualTo(422);
        assertThat(subir(expediente, token, pdf, "a.pdf", Map.of("tipo_documento", "PLIEGO", "numero_adenda", "3")).estado())
                .isEqualTo(422);
        assertThat(subir(expediente, token, pdf, "a.pdf", Map.of("tipo_documento", "PLIEGO", "numero_adenda", "x")).estado())
                .isEqualTo(422);
        assertThat(archivosEfimeros()).isEmpty();
    }

    @Test
    void faltaElArchivoOEstaVacio() throws Exception {
        assertThat(subir(expediente, token, null, null, Map.of("tipo_documento", "PLIEGO")).estado()).isEqualTo(400);
        assertThat(subir(expediente, token, new byte[0], "vacio.pdf", Map.of("tipo_documento", "PLIEGO")).estado()).isEqualTo(400);
        assertThat(archivosEfimeros()).isEmpty();
    }

    @Test
    void elNombreOriginalNuncaSeUsaComoRuta() throws Exception {
        Respuesta r = subir(expediente, token, PdfsDePrueba.valido(1), "../../etc/passwd.pdf",
                Map.of("tipo_documento", "PLIEGO"));
        assertThat(r.estado()).isEqualTo(202);
        assertThat(r.cuerpo().get("nombre_archivo_original").asText()).isEqualTo("passwd.pdf");
        String docId = r.cuerpo().get("id").asText();
        esperarEstadoFinalDeValidacion(docId);
        assertThat(archivosEfimeros()).containsExactly(docId + ".pdf");

        // Con barras invertidas (estilo Windows) el nombre tampoco conserva separadores de ruta.
        Respuesta w = subir(expediente, token, PdfsDePrueba.valido(1), "..\\..\\etc\\passwd2.pdf",
                Map.of("tipo_documento", "PLIEGO"));
        assertThat(w.estado()).isEqualTo(202);
        assertThat(w.cuerpo().get("nombre_archivo_original").asText()).doesNotContain("/").doesNotContain("\\");
    }

    @Test
    void sinMultipartDa415() throws Exception {
        assertThat(enviarJson("POST", "/api/v1/expedientes/" + expediente + "/documentos", token, Map.of()).estado())
                .isEqualTo(415);
    }

    // ---------- duplicados ----------

    @Test
    void elMismoPdfDosVecesDa409ConElIdDelOriginal() throws Exception {
        byte[] pdf = PdfsDePrueba.valido(2);
        String primero = subirPliego(pdf).cuerpo().get("id").asText();
        Respuesta segundo = subirPliego(pdf);
        assertThat(segundo.estado()).isEqualTo(409);
        assertThat(segundo.cuerpo().get("detail").get("documento_id").asText()).isEqualTo(primero);
        esperarEstadoFinalDeValidacion(primero);
        // El segundo intento no dejo archivos propios.
        assertThat(archivosEfimeros()).containsExactly(primero + ".pdf");
    }

    @Test
    void unPdfRechazadoSePuedeVolverACargarCorregido() throws Exception {
        // Mismo contenido infectado: tras el rechazo (ERROR_PURGADO) no cuenta como duplicado.
        byte[] infectado = PdfsDePrueba.conEicar();
        esperarEstadoFinalDeValidacion(subirPliego(infectado).cuerpo().get("id").asText());
        Respuesta otra = subirPliego(infectado);
        assertThat(otra.estado()).isEqualTo(202);
        esperarEstadoFinalDeValidacion(otra.cuerpo().get("id").asText());
    }

    // ---------- permisos ----------

    @Test
    void soloUnEditorPuedeSubirYUnLectorPuedeConsultar() throws Exception {
        String correo = "lector-" + UUID.randomUUID() + "@x.co";
        enviarJson("POST", "/api/v1/usuarios", token, Map.of("email", correo, "password", PASS,
                "nombre_completo", "Lector", "rol_global", "LECTOR"));
        String idLector = get("/api/v1/usuarios", token).cuerpo().get(1).get("id").asText();
        enviarJson("PUT", "/api/v1/expedientes/" + expediente + "/permisos/" + idLector, token, Map.of("permiso", "LECTOR"));
        String tokenLector = enviarJson("POST", "/api/v1/auth/login", null, Map.of("email", correo, "password", PASS))
                .cuerpo().get("access_token").asText();

        String docId = subirPliego(PdfsDePrueba.valido(1)).cuerpo().get("id").asText();
        esperarEstadoFinalDeValidacion(docId);

        Respuesta prohibido = subir(expediente, tokenLector, PdfsDePrueba.valido(1), "x.pdf", Map.of("tipo_documento", "PLIEGO"));
        assertThat(prohibido.estado()).isEqualTo(403);
        assertThat(get("/api/v1/expedientes/" + expediente + "/documentos", tokenLector).cuerpo()).hasSize(1);
        assertThat(get("/api/v1/expedientes/" + expediente + "/documentos/" + docId, tokenLector).estado()).isEqualTo(200);
        assertThat(enviarJson("DELETE", "/api/v1/expedientes/" + expediente + "/documentos/" + docId, tokenLector, null).estado())
                .isEqualTo(403);
    }

    @Test
    void otroTenantNoPuedeSubirNiVerDocumentos() throws Exception {
        String docId = subirPliego(PdfsDePrueba.valido(1)).cuerpo().get("id").asText();
        esperarEstadoFinalDeValidacion(docId);
        String tokenB = enviarJson("POST", "/api/v1/auth/registro-tenant", null, Map.of("tenant_nombre", "Otro Hospital",
                "nit", "NIT-" + UUID.randomUUID(), "admin_email", "b-" + UUID.randomUUID() + "@x.co",
                "admin_password", PASS, "admin_nombre", "Admin B")).cuerpo().get("access_token").asText();

        assertThat(subir(expediente, tokenB, PdfsDePrueba.valido(1), "x.pdf", Map.of("tipo_documento", "PLIEGO")).estado())
                .isEqualTo(404);
        assertThat(get("/api/v1/expedientes/" + expediente + "/documentos", tokenB).estado()).isEqualTo(404);
        assertThat(get("/api/v1/expedientes/" + expediente + "/documentos/" + docId, tokenB).estado()).isEqualTo(404);
    }

    @Test
    void unExpedienteCerradoNoAceptaSubidas() throws Exception {
        enviarJson("PATCH", "/api/v1/expedientes/" + expediente, token, Map.of("estado", "CERRADO"));
        Respuesta r = subirPliego(PdfsDePrueba.valido(1));
        assertThat(r.estado()).isEqualTo(409);
        assertThat(r.cuerpo().get("detail").asText()).isEqualTo("El expediente no está abierto");
        assertThat(archivosEfimeros()).isEmpty();
    }

    @Test
    void noSeAceptaSubirDuranteUnaReindexacion() throws Exception {
        String usuario = jdbc.queryForObject("select id::text from usuarios limit 1", String.class);
        jdbc.update("insert into reindexaciones (tenant_id, expediente_id, modelo_origen, modelo_destino, estado, created_by) "
                + "select tenant_id, id, 'a', 'b', 'EN_PROCESO', ?::uuid from expedientes", usuario);
        assertThat(subirPliego(PdfsDePrueba.valido(1)).estado()).isEqualTo(409);
        assertThat(archivosEfimeros()).isEmpty();
    }

    // ---------- eliminacion ----------

    @Test
    void eliminarUnDocumentoBorraElArchivoYConservaElActa() throws Exception {
        String docId = subirPliego(PdfsDePrueba.valido(1)).cuerpo().get("id").asText();
        esperarEstadoFinalDeValidacion(docId);
        assertThat(archivosEfimeros()).containsExactly(docId + ".pdf");

        Respuesta r = enviarJson("DELETE", "/api/v1/expedientes/" + expediente + "/documentos/" + docId, token, null);
        assertThat(r.estado()).isEqualTo(204);
        assertThat(archivosEfimeros()).isEmpty();
        assertThat(get("/api/v1/expedientes/" + expediente + "/documentos/" + docId, token).estado()).isEqualTo(404);
        // El acta sobrevive (con el documento ya desligado) y registra que el archivo existia.
        Integer actas = jdbc.queryForObject(
                "select count(*) from actas_purga where motivo='DOCUMENTO_ELIMINADO' and archivo_existia", Integer.class);
        assertThat(actas).isEqualTo(1);
    }

    @Test
    void eliminarElExpedienteBorraLosPdfTemporalesPendientes() throws Exception {
        String docId = subirPliego(PdfsDePrueba.valido(1)).cuerpo().get("id").asText();
        esperarEstadoFinalDeValidacion(docId);
        assertThat(archivosEfimeros()).containsExactly(docId + ".pdf");
        assertThat(enviarJson("DELETE", "/api/v1/expedientes/" + expediente, token, null).estado()).isEqualTo(204);
        assertThat(archivosEfimeros()).isEmpty();
    }

    // ---------- concurrencia ----------

    @Test
    void variasSubidasSimultaneasNoSePisan() throws Exception {
        int n = 8;
        List<byte[]> pdfs = new java.util.ArrayList<>();
        for (int i = 0; i < n; i++) pdfs.add(PdfsDePrueba.valido(1 + i % 3));
        var resultados = new LinkedHashMap<Integer, Respuesta>();
        try (var pool = java.util.concurrent.Executors.newFixedThreadPool(n)) {
            var futuros = new java.util.ArrayList<java.util.concurrent.Future<Respuesta>>();
            for (byte[] pdf : pdfs) futuros.add(pool.submit(() -> subirPliego(pdf)));
            for (int i = 0; i < n; i++) resultados.put(i, futuros.get(i).get());
        }
        for (var r : resultados.values()) {
            assertThat(r.estado()).isEqualTo(202);
            esperarEstadoFinalDeValidacion(r.cuerpo().get("id").asText());
        }
        assertThat(archivosEfimeros()).hasSize(n).allMatch(nombre -> nombre.endsWith(".pdf"));
        assertThat(Infra.AGENTE.llamadas()).hasSize(n);
    }
}

package co.medtender.api;

import co.medtender.api.privacidad.CorreoEnvio;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.sql.DriverManager;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.regex.Pattern;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.ResultActions;
import tools.jackson.databind.JsonNode;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Cuidadores: una persona comparte UN expediente por invitación de correo, de solo lectura o para subir
 * documentos. Lo que no está permitido de forma expresa queda cerrado, y la base de datos lo limita a ese
 * expediente aunque la API se equivocara.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Import(ComparticionesIT.Buzon.class)
class ComparticionesIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";
    private static final String ANA = "ana@correo.co";
    private static final String LUIS = "luis@correo.co";
    static final List<String[]> ENVIADOS = new CopyOnWriteArrayList<>();

    @TestConfiguration
    static class Buzon {
        @Bean
        @Primary
        CorreoEnvio correoDePrueba() {
            return (para, asunto, cuerpo) -> ENVIADOS.add(new String[] {para, asunto, cuerpo});
        }
    }

    @LocalServerPort int puerto;

    private JsonNode ana;
    private JsonNode luis;
    private String expediente;
    private String otro;

    @BeforeEach
    void preparar() throws Exception {
        ana = persona(ANA, "Ana Pérez");
        luis = persona(LUIS, "Luis Gómez");
        expediente = crearExpediente(ana, "MAMA");
        otro = crearExpediente(ana, "PRIVADO");
        ENVIADOS.clear();
    }

    // ---------- utilidades ----------

    private JsonNode persona(String email, String nombre) throws Exception {
        var r = mvc.perform(post("/api/v1/auth/registro-personal").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("nombre", nombre, "email", email, "password", PASS)))).andReturn();
        assertThat(r.getResponse().getStatus()).isEqualTo(201);
        JsonNode tokens = cuerpo(r);
        aceptarConsentimiento(tokens).andExpect(status().isOk());
        return tokens;
    }

    private ResultActions invitar(JsonNode quien, String exp, String correo, String permiso) throws Exception {
        return mvc.perform(post("/api/v1/expedientes/" + exp + "/comparticiones").header("Authorization", bearer(quien))
                .contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("correo", correo, "permiso", permiso))));
    }

    private ResultActions aceptar(JsonNode quien, String token) throws Exception {
        return mvc.perform(post("/api/v1/invitaciones/aceptar").header("Authorization", bearer(quien))
                .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("token", token))));
    }

    private static String tokenDelCorreo(String para) {
        var patron = Pattern.compile("/invitacion\\?token=([0-9a-f]{64})");
        for (int i = ENVIADOS.size() - 1; i >= 0; i--) {
            var m = patron.matcher(ENVIADOS.get(i)[2]);
            if (ENVIADOS.get(i)[0].equals(para) && m.find()) return m.group(1);
        }
        throw new AssertionError("No llegó la invitación a " + para);
    }

    private void compartir(String permiso) throws Exception {
        invitar(ana, expediente, LUIS, permiso).andExpect(status().isCreated());
        aceptar(luis, tokenDelCorreo(LUIS)).andExpect(status().isOk());
    }

    private ResultActions ver(JsonNode quien, String ruta) throws Exception {
        return mvc.perform(getAuth(ruta, quien));
    }

    private UUID tenantDe(String email) {
        return jdbc.queryForObject("select tenant_id from usuarios where email = ?", UUID.class, email);
    }

    private UUID idDe(String email) {
        return jdbc.queryForObject("select id from usuarios where email = ?", UUID.class, email);
    }

    private int subir(JsonNode quien, String exp) throws Exception {
        String limite = "----medtender" + UUID.randomUUID();
        var partes = new java.io.ByteArrayOutputStream();
        partes.write(("--" + limite + "\r\nContent-Disposition: form-data; name=\"tipo_documento\"\r\n\r\nHISTORIA_CLINICA\r\n"
                + "--" + limite + "\r\nContent-Disposition: form-data; name=\"archivo\"; filename=\"examen.pdf\"\r\n"
                + "Content-Type: application/pdf\r\n\r\n").getBytes(StandardCharsets.UTF_8));
        partes.write(PdfsDePrueba.valido(1));
        partes.write(("\r\n--" + limite + "--\r\n").getBytes(StandardCharsets.UTF_8));
        var pedido = HttpRequest.newBuilder(URI.create("http://localhost:" + puerto + "/api/v1/expedientes/" + exp + "/documentos"))
                .header("Authorization", bearer(quien)).header("Content-Type", "multipart/form-data; boundary=" + limite)
                .POST(HttpRequest.BodyPublishers.ofByteArray(partes.toByteArray())).build();
        return HttpClient.newHttpClient().send(pedido, HttpResponse.BodyHandlers.ofString()).statusCode();
    }

    // ---------- invitar y aceptar ----------

    @Test
    void laInvitacionNoLlevaDatosDeSaludYNadaSeVeHastaAceptarla() throws Exception {
        invitar(ana, expediente, "  Luis@Correo.co ", "LECTOR").andExpect(status().isCreated())
                .andExpect(jsonPath("$.estado").value("PENDIENTE")).andExpect(jsonPath("$.correo").value(LUIS));
        assertThat(ENVIADOS).hasSize(1);
        String correo = ENVIADOS.get(0)[1] + "\n" + ENVIADOS.get(0)[2];
        assertThat(correo).contains("Ana Pérez").doesNotContain("MAMA", "Licitación MAMA");
        // Solo se guarda la huella del enlace.
        assertThat(jdbc.queryForObject("select token_hash from comparticiones", String.class)).isNotEqualTo(tokenDelCorreo(LUIS));

        ver(luis, "/api/v1/expedientes/" + expediente).andExpect(status().isNotFound());
        ver(luis, "/api/v1/compartidos").andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(0));

        String token = tokenDelCorreo(LUIS);
        ENVIADOS.clear();
        aceptar(luis, token).andExpect(status().isOk()).andExpect(jsonPath("$.expediente_id").value(expediente));
        assertThat(ENVIADOS).extracting(e -> e[0]).containsExactly(ANA); // aviso a la dueña
        assertThat(ENVIADOS.get(0)[2]).contains("Luis Gómez").doesNotContain("MAMA");
        assertThat(enLaAuditoriaDeAna("COMPARTICION_ACEPTADA")).isEqualTo(1);
    }

    private int enLaAuditoriaDeAna(String accion) {
        return jdbc.queryForObject("select count(*) from auditoria where accion = ? and tenant_id = ?", Integer.class,
                accion, tenantDe(ANA));
    }

    @Test
    void elEnlaceSoloSirveUnaVezParaElCorreoInvitadoYMientrasNoVenza() throws Exception {
        JsonNode eva = persona("eva@correo.co", "Eva Ruiz");
        invitar(ana, expediente, LUIS, "LECTOR").andExpect(status().isCreated());
        String primero = tokenDelCorreo(LUIS);
        aceptar(eva, primero).andExpect(status().isNotFound());
        aceptar(luis, "0".repeat(64)).andExpect(status().isNotFound());

        invitar(ana, expediente, LUIS, "LECTOR").andExpect(status().isCreated());
        aceptar(luis, primero).andExpect(status().isNotFound()); // el anterior dejó de valer
        String segundo = tokenDelCorreo(LUIS);
        jdbc.update("update comparticiones set expira_at = now() - interval '1 minute' where estado = 'PENDIENTE'");
        aceptar(luis, segundo).andExpect(status().isNotFound());

        invitar(ana, expediente, LUIS, "LECTOR").andExpect(status().isCreated());
        String tercero = tokenDelCorreo(LUIS);
        aceptar(luis, tercero).andExpect(status().isOk());
        aceptar(luis, tercero).andExpect(status().isNotFound());
        invitar(ana, expediente, LUIS, "EDITOR").andExpect(status().isConflict()); // ya tiene acceso
    }

    @Test
    void soloCuentasPersonalesYSinInvitarseASiMismaNiPasarDeCinco() throws Exception {
        JsonNode admin = registrarTenant("930077", "admin@hospital.co", PASS);
        invitar(admin, crearExpediente(admin, "ORG"), LUIS, "LECTOR").andExpect(status().isForbidden());
        invitar(ana, expediente, ANA, "LECTOR").andExpect(status().isUnprocessableContent());
        invitar(ana, expediente, LUIS, "ADMIN").andExpect(status().isUnprocessableContent());
        invitar(ana, expediente, "no-es-correo", "LECTOR").andExpect(status().isUnprocessableContent());
        invitar(luis, expediente, "eva@correo.co", "LECTOR").andExpect(status().isNotFound()); // no es suyo
        for (int i = 1; i <= 5; i++) {
            invitar(ana, expediente, "f" + i + "@correo.co", "LECTOR").andExpect(status().isCreated());
        }
        invitar(ana, expediente, "f6@correo.co", "LECTOR").andExpect(status().isConflict());
        // una cuenta de organización no puede aceptar
        invitar(ana, otro, "admin@hospital.co", "LECTOR").andExpect(status().isCreated());
        aceptar(admin, tokenDelCorreo("admin@hospital.co")).andExpect(status().isForbidden());
    }

    // ---------- qué puede y qué no puede el cuidador ----------

    @Test
    void conLecturaVeYPreguntaSoloSobreEseExpediente() throws Exception {
        compartir("LECTOR");
        ver(luis, "/api/v1/expedientes/" + expediente).andExpect(status().isOk())
                .andExpect(jsonPath("$.mi_permiso").value("LECTOR"))
                .andExpect(jsonPath("$.compartido_por").value("Ana Pérez"));
        ver(luis, "/api/v1/expedientes/" + expediente + "/documentos").andExpect(status().isOk());
        ver(luis, "/api/v1/compartidos").andExpect(jsonPath("$[0].expediente_id").value(expediente))
                .andExpect(jsonPath("$[0].compartido_por").value("Ana Pérez"));
        // su lista de expedientes sigue siendo la suya
        ver(luis, "/api/v1/expedientes").andExpect(jsonPath("$.length()").value(0));

        Infra.AGENTE.responder("POST /internal/v1/consultas", 200, "{\"consultaId\":\"c\",\"sinEvidencia\":true,\"citas\":[]}");
        mvc.perform(post("/api/v1/expedientes/" + expediente + "/consultas").header("Authorization", bearer(luis))
                .contentType(MediaType.APPLICATION_JSON).content("{\"pregunta\":\"¿Qué dice el examen?\"}"))
                .andExpect(status().isOk());
        var llamada = Infra.AGENTE.llamadas().get(Infra.AGENTE.llamadas().size() - 1);
        assertThat(llamada.cuerpo()).contains(tenantDe(ANA).toString(), expediente, idDe(LUIS).toString())
                .doesNotContain(tenantDe(LUIS).toString());

        // queda en la auditoría de la dueña, a nombre de quien entró
        assertThat(jdbc.queryForObject("select count(*) from auditoria where accion='CONSULTA_RAG' and tenant_id=? and usuario_id=?",
                Integer.class, tenantDe(ANA), idDe(LUIS))).isEqualTo(1);

        assertThat(subir(luis, expediente)).isEqualTo(403);
        ver(luis, "/api/v1/expedientes/" + otro).andExpect(status().isNotFound());
        ver(luis, "/api/v1/expedientes/" + otro + "/documentos").andExpect(status().isNotFound());
    }

    @Test
    void conEdicionPuedeSubirYElDocumentoQuedaEnElExpedienteDeLaDuena() throws Exception {
        compartir("EDITOR");
        assertThat(subir(luis, expediente)).isEqualTo(202);
        assertThat(jdbc.queryForObject("select tenant_id from documentos where expediente_id = ?", UUID.class,
                UUID.fromString(expediente))).isEqualTo(tenantDe(ANA));
        ver(ana, "/api/v1/expedientes/" + expediente + "/documentos").andExpect(jsonPath("$.length()").value(1));
        String doc = jdbc.queryForObject("select id::text from documentos", String.class);
        ver(luis, "/api/v1/expedientes/" + expediente + "/documentos/" + doc).andExpect(status().isOk());
    }

    @Test
    void ningunaAccionDeLaDuenaQuedaAbiertaAlCuidador() throws Exception {
        compartir("EDITOR");
        assertThat(subir(ana, expediente)).isEqualTo(202);
        String doc = jdbc.queryForObject("select id::text from documentos", String.class);
        String base = "/api/v1/expedientes/" + expediente;
        for (var pedido : List.of(
                delete(base), delete(base + "/documentos/" + doc), delete(base + "/consultas"),
                patch(base).contentType(MediaType.APPLICATION_JSON).content("{\"titulo\":\"otro\"}"),
                put(base + "/permisos/" + idDe(LUIS)).contentType(MediaType.APPLICATION_JSON).content("{\"permiso\":\"ADMIN\"}"),
                post(base + "/reindexaciones").contentType(MediaType.APPLICATION_JSON).content("{\"embedding_model\":\"x\"}"),
                post(base + "/comparticiones").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"correo\":\"eva@correo.co\",\"permiso\":\"LECTOR\"}"))) {
            mvc.perform(pedido.header("Authorization", bearer(luis))).andExpect(status().isNotFound());
        }
        ver(luis, base + "/permisos").andExpect(status().isNotFound());
        ver(luis, base + "/comparticiones").andExpect(status().isNotFound());
        assertThat(jdbc.queryForObject("select count(*) from documentos", Integer.class)).isEqualTo(1);
    }

    @Test
    void necesitaSuPropioConsentimientoParaUsarElAsistente() throws Exception {
        compartir("LECTOR");
        jdbc.update("delete from consentimientos where usuario_id = ?", idDe(LUIS));
        mvc.perform(post("/api/v1/expedientes/" + expediente + "/consultas").header("Authorization", bearer(luis))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"pregunta\":\"¿Qué dice?\"}"))
                .andExpect(status().isForbidden()).andExpect(jsonPath("$.codigo").value("consentimiento_requerido"));
    }

    // ---------- recordatorios de cada quien, revocar y borrar ----------

    private void proponerRecordatorio(JsonNode quien) throws Exception {
        Infra.AGENTE.responder("POST /internal/v1/recordatorios/propuestas", 200, """
                {"lineaGuardada":true,"propuestas":[{"texto":"Control en 3 meses","fechaTexto":"en 3 meses",
                 "fechaDocumento":null,"fechaPropuesta":null,"cita":{"documentoId":"d1","extractoLiteral":"Control en 3 meses"}}]}""");
        mvc.perform(post("/api/v1/expedientes/" + expediente + "/recordatorios/propuestas").header("Authorization", bearer(quien)))
                .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(1));
    }

    @Test
    void losRecordatoriosDeCadaQuienSonSuyosYSeBorranAlPerderElAcceso() throws Exception {
        compartir("LECTOR");
        proponerRecordatorio(ana);
        proponerRecordatorio(luis);
        ver(luis, "/api/v1/recordatorios").andExpect(jsonPath("$.length()").value(1));
        ver(ana, "/api/v1/recordatorios").andExpect(jsonPath("$.length()").value(1));
        assertThat(jdbc.queryForObject("select tenant_id from recordatorios where usuario_id=?", UUID.class, idDe(LUIS)))
                .isEqualTo(tenantDe(LUIS));
        String suyo = jdbc.queryForObject("select id::text from recordatorios where usuario_id=?", String.class, idDe(LUIS));
        mvc.perform(patch("/api/v1/recordatorios/" + suyo).header("Authorization", bearer(luis))
                .contentType(MediaType.APPLICATION_JSON).content("{\"estado\":\"CONFIRMADO\",\"fecha\":\"2027-01-10\"}"))
                .andExpect(status().isOk());

        String comparticion = jdbc.queryForObject("select id::text from comparticiones where estado='ACEPTADA'", String.class);
        mvc.perform(delete("/api/v1/expedientes/" + expediente + "/comparticiones/" + comparticion)
                .header("Authorization", bearer(ana))).andExpect(status().isNoContent());

        ver(luis, "/api/v1/expedientes/" + expediente).andExpect(status().isNotFound());
        ver(luis, "/api/v1/recordatorios").andExpect(jsonPath("$.length()").value(0));
        ver(ana, "/api/v1/recordatorios").andExpect(jsonPath("$.length()").value(1));
    }

    @Test
    void elCuidadorPuedeSalirYLaDuenaSeEntera() throws Exception {
        compartir("LECTOR");
        ENVIADOS.clear();
        mvc.perform(delete("/api/v1/compartidos/" + expediente).header("Authorization", bearer(luis)))
                .andExpect(status().isNoContent());
        ver(luis, "/api/v1/expedientes/" + expediente).andExpect(status().isNotFound());
        assertThat(ENVIADOS).extracting(e -> e[0]).containsExactly(ANA);
        assertThat(enLaAuditoriaDeAna("COMPARTICION_REVOCADA")).isEqualTo(1);
    }

    @Test
    void laDuenaVeQuienTieneAccesoYCuandoEntroPorUltimaVez() throws Exception {
        compartir("LECTOR");
        String ruta = "/api/v1/expedientes/" + expediente + "/comparticiones";
        ver(ana, ruta).andExpect(jsonPath("$[0].correo").value(LUIS)).andExpect(jsonPath("$[0].estado").value("ACEPTADA"))
                .andExpect(jsonPath("$[0].ultimo_acceso").doesNotExist());
        ver(luis, "/api/v1/expedientes/" + expediente).andExpect(status().isOk());
        ver(ana, ruta).andExpect(jsonPath("$[0].ultimo_acceso").isNotEmpty());
        ver(luis, "/api/v1/expedientes/" + expediente).andExpect(status().isOk());
        assertThat(jdbc.queryForObject("select count(*) from auditoria where accion='ACCESO_COMPARTIDO' and tenant_id=?",
                Integer.class, tenantDe(ANA))).isEqualTo(1); // una anotación aunque entre varias veces seguidas
    }

    @Test
    void borrarCualquieraDeLasDosCuentasNoDejaRestosNiFalla() throws Exception {
        compartir("LECTOR");
        proponerRecordatorio(luis);
        jdbc.update("""
                insert into consultas (tenant_id, expediente_id, usuario_id, pregunta, respuesta, sin_evidencia,
                    modelo_embeddings, latencia_ms) values (?, ?, ?, 'p', '{}'::jsonb, true, 'gemini-embedding-001', 1)""",
                tenantDe(ANA), UUID.fromString(expediente), idDe(LUIS));
        mvc.perform(post("/api/v1/cuenta/eliminar").header("Authorization", bearer(luis))
                .contentType(MediaType.APPLICATION_JSON).content("{\"password\":\"" + PASS + "\"}"))
                .andExpect(status().isNoContent());
        assertThat(jdbc.queryForObject("select count(*) from comparticiones", Integer.class)).isZero();
        assertThat(jdbc.queryForObject("select count(*) from consultas", Integer.class)).isZero();
        assertThat(jdbc.queryForObject("select count(*) from recordatorios", Integer.class)).isZero();
        ver(ana, "/api/v1/expedientes/" + expediente).andExpect(status().isOk());

        JsonNode eva = persona("eva@correo.co", "Eva Ruiz");
        invitar(ana, expediente, "eva@correo.co", "LECTOR").andExpect(status().isCreated());
        aceptar(eva, tokenDelCorreo("eva@correo.co")).andExpect(status().isOk());
        proponerRecordatorio(eva);
        mvc.perform(post("/api/v1/cuenta/eliminar").header("Authorization", bearer(ana))
                .contentType(MediaType.APPLICATION_JSON).content("{\"password\":\"" + PASS + "\"}"))
                .andExpect(status().isNoContent());
        assertThat(jdbc.queryForObject("select count(*) from comparticiones", Integer.class)).isZero();
        assertThat(jdbc.queryForObject("select count(*) from recordatorios", Integer.class)).isZero();
        ver(eva, "/api/v1/compartidos").andExpect(jsonPath("$.length()").value(0));
    }

    @Test
    void descargarMisDatosDiceConQuienCompartoYNoDaDatosAjenosAlCuidador() throws Exception {
        compartir("LECTOR");
        proponerRecordatorio(luis);
        String deAna = exportar(ana);
        assertThat(deAna).contains("compartido_con", LUIS, "ACEPTADA").doesNotContain("token_hash");
        String deLuis = exportar(luis);
        assertThat(deLuis).contains("Control en 3 meses", "Expediente que comparten contigo").doesNotContain("MAMA", ANA);
    }

    private String exportar(JsonNode quien) throws Exception {
        byte[] zip = mvc.perform(post("/api/v1/cuenta/exportar").header("Authorization", bearer(quien))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"password\":\"" + PASS + "\"}"))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsByteArray();
        try (var entradas = new java.util.zip.ZipInputStream(new java.io.ByteArrayInputStream(zip))) {
            for (var e = entradas.getNextEntry(); e != null; e = entradas.getNextEntry()) {
                if (e.getName().equals("datos.json")) return new String(entradas.readAllBytes(), StandardCharsets.UTF_8);
            }
        }
        throw new AssertionError("sin datos.json");
    }

    // ---------- la segunda barrera: la base de datos ----------

    @Test
    void aunqueLaApiSeEquivocaraLaBaseSoloEntregaElExpedienteCompartido() throws Exception {
        compartir("LECTOR");
        assertThat(subir(ana, expediente)).isEqualTo(202);
        assertThat(subir(ana, otro)).isEqualTo(202);
        try (var c = DriverManager.getConnection(Infra.POSTGRES.getJdbcUrl(), Infra.APP_USUARIO, Infra.APP_PASSWORD); var s = c.createStatement()) {
            s.execute("select set_config('app.tenant_id', '" + tenantDe(ANA) + "', false), set_config('app.sistema','off',false),"
                    + " set_config('app.expediente_invitado', '" + expediente + "', false)");
            var vistos = new ArrayList<Integer>();
            for (String sql : List.of("select count(*) from expedientes", "select count(*) from documentos",
                    "select count(*) from documentos where expediente_id = '" + otro + "'", "select count(*) from usuarios",
                    "select count(*) from tenants", "select count(*) from consentimientos", "select count(*) from sesiones",
                    "select count(*) from comparticiones", "select count(*) from auditoria")) {
                try (var r = s.executeQuery(sql)) {
                    r.next();
                    vistos.add(r.getInt(1));
                }
            }
            assertThat(vistos).containsExactly(1, 1, 0, 0, 0, 0, 0, 0, 0);
            assertThat(s.executeUpdate("update expedientes set titulo = 'x' where id = '" + otro + "'")).isZero();
            assertThat(s.executeUpdate("delete from documentos where expediente_id = '" + otro + "'")).isZero();
        }
    }
}

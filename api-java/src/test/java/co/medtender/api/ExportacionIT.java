package co.medtender.api;

import com.fasterxml.jackson.databind.JsonNode;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.ResultActions;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** «Descargar mis datos»: todo lo de la persona, solo lo suyo y sin secretos. */
class ExportacionIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";

    private JsonNode registrarPersonal(String email) throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/auth/registro-personal").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("nombre", "Ana Pérez", "email", email, "password", PASS)))).andReturn();
        assertThat(r.getResponse().getStatus()).isEqualTo(201);
        return cuerpo(r);
    }

    private ResultActions exportar(JsonNode tokens, String password) throws Exception {
        return mvc.perform(post("/api/v1/cuenta/exportar").header("Authorization", bearer(tokens))
                .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("password", password))));
    }

    /** Un documento con un fragmento, una pregunta con su respuesta y un recordatorio. */
    private void sembrar(String expedienteId, String email, String texto, String pregunta) {
        var u = jdbc.queryForMap("select id, tenant_id from usuarios where email = ?", email);
        UUID usuario = (UUID) u.get("id");
        UUID tenant = (UUID) u.get("tenant_id");
        UUID exp = UUID.fromString(expedienteId);
        UUID doc = UUID.randomUUID();
        jdbc.update("""
                insert into documentos (id, tenant_id, expediente_id, nombre_archivo_original, tipo_documento, sha256_original,
                    tamano_bytes, total_paginas, estado_indexacion, embedding_model)
                values (?, ?, ?, 'examen.pdf', 'HISTORIA_CLINICA', ?, 10, 3, 'INDEXADO_Y_PURGADO', 'gemini-embedding-001')""",
                doc, tenant, exp, "a".repeat(64));
        jdbc.update("""
                insert into fragmentos (tenant_id, expediente_id, documento_id, orden, pagina_inicio, pagina_fin, seccion,
                    contenido_texto, contenido_vectorizado, token_count, embedding_model)
                values (?, ?, ?, 1, 2, 3, 'Resultados', ?, 'VECTORIZADO-INTERNO', 5, 'gemini-embedding-001')""",
                tenant, exp, doc, texto);
        jdbc.update("""
                insert into consultas (tenant_id, expediente_id, usuario_id, pregunta, respuesta, sin_evidencia,
                    modelo_embeddings, modelo_llm, latencia_ms)
                values (?, ?, ?, ?, ?::jsonb, false, 'gemini-embedding-001', 'gemini-2.5-flash', 100)""",
                tenant, exp, usuario, pregunta, "{\"respuestaAnalitica\":\"La hemoglobina es 13,2 g/dL.\"}");
        jdbc.update("""
                insert into recordatorios (tenant_id, usuario_id, expediente_id, texto, estado, cita, clave)
                values (?, ?, ?, 'Control en tres meses', 'PROPUESTO', '{}'::jsonb, ?)""",
                tenant, usuario, exp, UUID.randomUUID().toString().replace("-", "").repeat(2));
    }

    private static Map<String, String> abrir(byte[] zip) throws Exception {
        var archivos = new LinkedHashMap<String, String>();
        try (var in = new ZipInputStream(new ByteArrayInputStream(zip))) {
            for (ZipEntry e = in.getNextEntry(); e != null; e = in.getNextEntry()) {
                archivos.put(e.getName(), new String(in.readAllBytes(), StandardCharsets.UTF_8));
            }
        }
        return archivos;
    }

    @Test
    void traeLoQueHayDeLaPersonaEnJsonYEnUnaVersionLegible() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        aceptarConsentimiento(ana).andExpect(status().isOk());
        String exp = crearExpediente(ana, "MIS-EXAMENES");
        sembrar(exp, "ana@correo.co", "Hemoglobina 13,2 g/dL", "¿Qué dice mi examen?");

        byte[] zip = exportar(ana, PASS).andExpect(status().isOk())
                .andExpect(header().string("Content-Type", "application/zip"))
                .andExpect(header().string("Cache-Control", "no-store"))
                .andExpect(header().string("Content-Disposition", org.hamcrest.Matchers.matchesPattern(
                        "attachment; filename=\"medtender-mis-datos-\\d{4}-\\d{2}-\\d{2}\\.zip\"")))
                .andReturn().getResponse().getContentAsByteArray();
        var archivos = abrir(zip);
        assertThat(archivos.keySet()).containsExactlyInAnyOrder("LEEME.txt", "datos.json", "resumen.html");

        JsonNode datos = json.readTree(archivos.get("datos.json"));
        assertThat(datos.at("/cuenta/correo").asText()).isEqualTo("ana@correo.co");
        assertThat(datos.at("/cuenta/nombre").asText()).isEqualTo("Ana Pérez");
        assertThat(datos.at("/consentimientos/0/version").asText()).isEqualTo("2026-11-v3");
        assertThat(datos.at("/expedientes/0/titulo").asText()).isNotBlank();
        assertThat(datos.at("/expedientes/0/documentos/0/nombre").asText()).isEqualTo("examen.pdf");
        assertThat(datos.at("/expedientes/0/documentos/0/fragmentos/0/texto").asText()).isEqualTo("Hemoglobina 13,2 g/dL");
        assertThat(datos.at("/expedientes/0/documentos/0/fragmentos/0/pagina_inicio").asInt()).isEqualTo(2);
        assertThat(datos.at("/expedientes/0/consultas/0/pregunta").asText()).isEqualTo("¿Qué dice mi examen?");
        assertThat(datos.at("/expedientes/0/consultas/0/respuesta/respuestaAnalitica").asText()).contains("13,2");
        assertThat(datos.at("/recordatorios/0/texto").asText()).isEqualTo("Control en tres meses");
        assertThat(datos.at("/accesos").size()).isPositive();

        assertThat(archivos.get("resumen.html")).contains("Hemoglobina 13,2 g/dL", "páginas 2–3", "La hemoglobina es 13,2 g/dL.");
        String todo = String.join("\n", archivos.values());
        assertThat(todo).doesNotContain("password", "$2a$", "$2b$", "totp", "VECTORIZADO-INTERNO", "embedding");
    }

    @Test
    void abreElHistorialQueElAgenteGuardaCifrado() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        String exp = crearExpediente(ana, "X-1");
        sembrar(exp, "ana@correo.co", "texto del documento", "se reemplaza");
        // Valor producido por el agente (ver CifradoDatosTest).
        jdbc.update("update consultas set pregunta = ?",
                "mtd1:U8IknwtEVCmpVmCN28hvegxsSy7iWTohvefpMJRvHhJ42eVRqaoPy1Zq8L//Aor1IU0c00yyPPWSYH2sDDsv+vG9nvRQhZI=");

        var archivos = abrir(exportar(ana, PASS).andExpect(status().isOk()).andReturn().getResponse().getContentAsByteArray());
        assertThat(archivos.get("datos.json")).contains("¿Cómo está mi hemoglobina? — año 2026").doesNotContain("mtd1:");
    }

    @Test
    void noMezclaDatosDeOtraCuenta() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        sembrar(crearExpediente(ana, "DE-ANA"), "ana@correo.co", "Texto de Ana", "pregunta de Ana");
        JsonNode luis = registrarPersonal("luis@correo.co");
        sembrar(crearExpediente(luis, "DE-LUIS"), "luis@correo.co", "Texto de Luis", "pregunta de Luis");

        var archivos = abrir(exportar(ana, PASS).andExpect(status().isOk()).andReturn().getResponse().getContentAsByteArray());
        String todo = String.join("\n", archivos.values());
        assertThat(todo).contains("Texto de Ana").doesNotContain("Texto de Luis", "pregunta de Luis", "luis@correo.co", "DE-LUIS");
    }

    @Test
    void elTextoDeLosDocumentosNoPuedeInyectarHtml() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        sembrar(crearExpediente(ana, "X-1"), "ana@correo.co", "<script>alert(1)</script>", "<img src=x onerror=alert(2)>");
        var archivos = abrir(exportar(ana, PASS).andReturn().getResponse().getContentAsByteArray());
        assertThat(archivos.get("resumen.html")).doesNotContain("<script>", "<img src=x").contains("&lt;script&gt;");
    }

    @Test
    void pideLaContrasenaYDejaConstanciaSinContenido() throws Exception {
        JsonNode ana = registrarPersonal("ana@correo.co");
        sembrar(crearExpediente(ana, "X-1"), "ana@correo.co", "Texto secreto de salud", "pregunta privada");

        exportar(ana, "Otra-Clave-123").andExpect(status().isForbidden());
        assertThat(jdbc.queryForObject("select count(*) from auditoria where accion='DATOS_EXPORTADOS'", Integer.class)).isZero();

        exportar(ana, PASS).andExpect(status().isOk());
        String detalle = jdbc.queryForObject("select detalle::text from auditoria where accion='DATOS_EXPORTADOS'", String.class);
        assertThat(detalle).contains("expedientes", "documentos").doesNotContain("secreto", "privada");
    }

    @Test
    void soloLasCuentasPersonalesYConUnLimitePorHora() throws Exception {
        JsonNode admin = registrarTenant("930002", "admin@hospital.co", PASS);
        exportar(admin, PASS).andExpect(status().isForbidden());

        JsonNode ana = registrarPersonal("ana@correo.co");
        for (int i = 0; i < 3; i++) {
            exportar(ana, PASS).andExpect(status().isOk());
        }
        exportar(ana, PASS).andExpect(status().isTooManyRequests());
    }
}

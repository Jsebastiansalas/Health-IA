package co.medtender.api;

import tools.jackson.databind.JsonNode;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class ExpedientesIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";

    @Test
    void crearExpedienteDejaAlCreadorComoAdminYUsaElModeloPorDefecto() throws Exception {
        JsonNode admin = registrarTenant("910001", "admin@a.co", PASS);
        crearUsuario(admin, "juridico@a.co", PASS, "JURIDICO");
        JsonNode juridico = login("juridico@a.co", PASS);

        mvc.perform(post("/api/v1/expedientes").header("Authorization", bearer(juridico))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of("codigo_expediente", "LIC-1", "titulo", "Pliego",
                                "tipo_expediente", "AUDITORIA_CLINICA"))))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.mi_permiso").value("ADMIN"))
                .andExpect(jsonPath("$.estado").value("ABIERTO"))
                .andExpect(jsonPath("$.embedding_model_activo").value("gemini-embedding-001"))
                .andExpect(jsonPath("$.embedding_dimension").value(1536));
    }

    @Test
    void codigoDuplicadoEnElTenantDa409PeroSePuedeRepetirEnOtroTenant() throws Exception {
        JsonNode adminA = registrarTenant("910002", "admin@b.co", PASS);
        JsonNode adminB = registrarTenant("910003", "admin@c.co", PASS);
        crearExpediente(adminA, "LIC-X");
        mvc.perform(post("/api/v1/expedientes").header("Authorization", bearer(adminA))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of("codigo_expediente", "LIC-X", "titulo", "Otro",
                                "tipo_expediente", "DOTACION_BIOMEDICA"))))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.detail").value("Ya existe un expediente con ese código"));
        crearExpediente(adminB, "LIC-X");
    }

    @Test
    void unLectorNoPuedeCrearExpedientes() throws Exception {
        JsonNode admin = registrarTenant("910004", "admin@d.co", PASS);
        crearUsuario(admin, "lector@d.co", PASS, "LECTOR");
        JsonNode lector = login("lector@d.co", PASS);
        mvc.perform(post("/api/v1/expedientes").header("Authorization", bearer(lector))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(Map.of("codigo_expediente", "L-1", "titulo", "No",
                                "tipo_expediente", "AUDITORIA_CLINICA"))))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.detail").value("Tu rol no puede crear expedientes"));
    }

    @Test
    void sinPermisoElExpedienteNoSeVeNiSeListaYConPermisoSi() throws Exception {
        JsonNode admin = registrarTenant("910005", "admin@e.co", PASS);
        String exp = crearExpediente(admin, "LIC-2");
        String idAuditor = crearUsuario(admin, "auditor@e.co", PASS, "AUDITOR_MEDICO");
        JsonNode auditor = login("auditor@e.co", PASS);

        mvc.perform(getAuth("/api/v1/expedientes/" + exp, auditor)).andExpect(status().isNotFound());
        assertThat(cuerpo(mvc.perform(getAuth("/api/v1/expedientes", auditor)).andReturn())).isEmpty();

        mvc.perform(put("/api/v1/expedientes/" + exp + "/permisos/" + idAuditor).header("Authorization", bearer(admin))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"permiso\":\"LECTOR\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.permiso").value("LECTOR"));

        mvc.perform(getAuth("/api/v1/expedientes/" + exp, auditor))
                .andExpect(status().isOk()).andExpect(jsonPath("$.mi_permiso").value("LECTOR"));
        JsonNode lista = cuerpo(mvc.perform(getAuth("/api/v1/expedientes", auditor)).andReturn());
        assertThat(lista).hasSize(1);
        assertThat(lista.get(0).get("mi_permiso").asString()).isEqualTo("LECTOR");

        // Un LECTOR no edita ni administra; un EDITOR edita pero no elimina.
        mvc.perform(patch("/api/v1/expedientes/" + exp).header("Authorization", bearer(auditor))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"titulo\":\"Nuevo\"}"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.detail").value("Se requiere permiso EDITOR"));
        mvc.perform(put("/api/v1/expedientes/" + exp + "/permisos/" + idAuditor).header("Authorization", bearer(admin))
                .contentType(MediaType.APPLICATION_JSON).content("{\"permiso\":\"EDITOR\"}")).andExpect(status().isOk());
        mvc.perform(patch("/api/v1/expedientes/" + exp).header("Authorization", bearer(auditor))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"titulo\":\"Nuevo\",\"estado\":\"CERRADO\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.titulo").value("Nuevo"))
                .andExpect(jsonPath("$.estado").value("CERRADO"));
        mvc.perform(delete("/api/v1/expedientes/" + exp).header("Authorization", bearer(auditor)))
                .andExpect(status().isForbidden());
        mvc.perform(get("/api/v1/expedientes/" + exp + "/permisos").header("Authorization", bearer(auditor)))
                .andExpect(status().isForbidden());
    }

    @Test
    void otroTenantNoVeElExpedienteYQuedaAuditado() throws Exception {
        JsonNode adminA = registrarTenant("910006", "admin@f.co", PASS);
        JsonNode adminB = registrarTenant("910007", "admin@g.co", PASS);
        String exp = crearExpediente(adminA, "LIC-3");

        mvc.perform(getAuth("/api/v1/expedientes/" + exp, adminB))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.detail").value("Expediente no encontrado"));
        mvc.perform(delete("/api/v1/expedientes/" + exp).header("Authorization", bearer(adminB)))
                .andExpect(status().isNotFound());
        assertThat(cuerpo(mvc.perform(getAuth("/api/v1/expedientes", adminB)).andReturn())).isEmpty();

        Integer denegados = jdbc.queryForObject(
                "select count(*) from auditoria where accion='ACCESO_DENEGADO' and resultado='DENEGADO' "
                        + "and detalle->>'motivo'='inexistente_o_otro_tenant'", Integer.class);
        assertThat(denegados).isEqualTo(2);
    }

    @Test
    void permisosNoSePuedenDarAUsuariosDeOtroTenantNiQuitarAlUltimoAdmin() throws Exception {
        JsonNode adminA = registrarTenant("910008", "admin@h.co", PASS);
        JsonNode adminB = registrarTenant("910009", "admin@i.co", PASS);
        String idB = crearUsuario(adminB, "u@i.co", PASS, "LECTOR");
        String exp = crearExpediente(adminA, "LIC-4");
        String idCreador = cuerpo(mvc.perform(getAuth("/api/v1/auth/me", adminA)).andReturn()).get("id").asString();

        mvc.perform(put("/api/v1/expedientes/" + exp + "/permisos/" + idB).header("Authorization", bearer(adminA))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"permiso\":\"LECTOR\"}"))
                .andExpect(status().isNotFound());

        // El creador es el unico ADMIN explicito: ni degradarlo ni revocarlo.
        mvc.perform(put("/api/v1/expedientes/" + exp + "/permisos/" + idCreador).header("Authorization", bearer(adminA))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"permiso\":\"LECTOR\"}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.detail").value("El expediente debe conservar al menos un ADMIN"));
        mvc.perform(delete("/api/v1/expedientes/" + exp + "/permisos/" + idCreador).header("Authorization", bearer(adminA)))
                .andExpect(status().isConflict());
    }

    @Test
    void revocarPermisoQuitaElAcceso() throws Exception {
        JsonNode admin = registrarTenant("910010", "admin@j.co", PASS);
        String exp = crearExpediente(admin, "LIC-5");
        String id = crearUsuario(admin, "u@j.co", PASS, "BIOMEDICO");
        JsonNode u = login("u@j.co", PASS);
        mvc.perform(put("/api/v1/expedientes/" + exp + "/permisos/" + id).header("Authorization", bearer(admin))
                .contentType(MediaType.APPLICATION_JSON).content("{\"permiso\":\"EDITOR\"}")).andExpect(status().isOk());
        mvc.perform(getAuth("/api/v1/expedientes/" + exp, u)).andExpect(status().isOk());

        mvc.perform(get("/api/v1/expedientes/" + exp + "/permisos").header("Authorization", bearer(admin)))
                .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(2));
        mvc.perform(delete("/api/v1/expedientes/" + exp + "/permisos/" + id).header("Authorization", bearer(admin)))
                .andExpect(status().isNoContent());
        mvc.perform(getAuth("/api/v1/expedientes/" + exp, u)).andExpect(status().isNotFound());
        mvc.perform(delete("/api/v1/expedientes/" + exp + "/permisos/" + id).header("Authorization", bearer(admin)))
                .andExpect(status().isNotFound());
    }

    @Test
    void eliminarExpedienteLoBorraYQuedaAuditado() throws Exception {
        JsonNode admin = registrarTenant("910011", "admin@k.co", PASS);
        String exp = crearExpediente(admin, "LIC-6");
        mvc.perform(delete("/api/v1/expedientes/" + exp).header("Authorization", bearer(admin)))
                .andExpect(status().isNoContent());
        mvc.perform(getAuth("/api/v1/expedientes/" + exp, admin)).andExpect(status().isNotFound());
        Integer eliminados = jdbc.queryForObject("select count(*) from auditoria where accion='EXPEDIENTE_ELIMINADO'", Integer.class);
        assertThat(eliminados).isEqualTo(1);
    }

    @Test
    void paginacionYValidacion() throws Exception {
        JsonNode admin = registrarTenant("910012", "admin@l.co", PASS);
        for (int i = 0; i < 3; i++) {
            crearExpediente(admin, "P-" + i);
        }
        assertThat(cuerpo(mvc.perform(getAuth("/api/v1/expedientes?limit=2", admin)).andReturn())).hasSize(2);
        assertThat(cuerpo(mvc.perform(getAuth("/api/v1/expedientes?limit=2&offset=2", admin)).andReturn())).hasSize(1);
        mvc.perform(getAuth("/api/v1/expedientes?limit=0", admin)).andExpect(status().isUnprocessableContent());
        mvc.perform(post("/api/v1/expedientes").header("Authorization", bearer(admin))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"codigo_expediente\":\"\",\"titulo\":\"x\",\"tipo_expediente\":\"OTRO\"}"))
                .andExpect(status().isUnprocessableContent());
    }
}

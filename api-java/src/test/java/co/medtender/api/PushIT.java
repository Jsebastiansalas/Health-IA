package co.medtender.api;

import co.medtender.api.privacidad.CorreoEnvio;
import co.medtender.api.push.DestinoPush;
import co.medtender.api.push.PushEnvio;
import co.medtender.api.push.Vapid;
import co.medtender.api.recordatorios.AvisosRecordatorios;
import java.math.BigInteger;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.Signature;
import java.security.interfaces.ECPrivateKey;
import java.security.interfaces.ECPublicKey;
import java.security.spec.ECGenParameterSpec;
import java.time.Instant;
import java.time.LocalDate;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.ResultActions;
import tools.jackson.databind.JsonNode;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** Notificaciones push de la app instalada: sin contenido, solo a servicios conocidos y con el correo de respaldo. */
@Import(PushIT.Dobles.class)
class PushIT extends IntegracionBase {

    private static final String PASS = "Clave-Segura-123";
    private static final String FCM = "https://fcm.googleapis.com/fcm/send/abc123";
    private static final String MOZILLA = "https://updates.push.services.mozilla.com/wpush/v2/def456";
    private static final KeyPair CLAVES = claves();
    private static final String PUBLICA = publica((ECPublicKey) CLAVES.getPublic());
    private static final String PRIVADA = escalar(((ECPrivateKey) CLAVES.getPrivate()).getS());

    static final List<String> PUSH = new CopyOnWriteArrayList<>();
    static final List<String> CORREOS = new CopyOnWriteArrayList<>();
    static volatile PushEnvio.Resultado respuesta = PushEnvio.Resultado.ENVIADO;

    @TestConfiguration
    static class Dobles {
        @Bean
        @Primary
        PushEnvio pushDePrueba() {
            return endpoint -> {
                PUSH.add(endpoint);
                return respuesta;
            };
        }

        @Bean
        @Primary
        CorreoEnvio correoDePrueba() {
            return (para, asunto, cuerpo) -> CORREOS.add(para);
        }
    }

    @DynamicPropertySource
    static void clavesDePrueba(DynamicPropertyRegistry r) {
        r.add("medtender.push.clave-publica", () -> PUBLICA);
        r.add("medtender.push.clave-privada", () -> PRIVADA);
    }

    private static KeyPair claves() {
        try {
            var g = KeyPairGenerator.getInstance("EC");
            g.initialize(new ECGenParameterSpec("secp256r1"));
            return g.generateKeyPair();
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    /** 32 bytes sin signo, como los entregan los navegadores y las herramientas de VAPID. */
    private static byte[] fijo(BigInteger n) {
        byte[] b = n.toByteArray();
        byte[] salida = new byte[32];
        int largo = Math.min(32, b.length);
        System.arraycopy(b, b.length - largo, salida, 32 - largo, largo);
        return salida;
    }

    private static String escalar(BigInteger n) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(fijo(n));
    }

    private static String publica(ECPublicKey k) {
        byte[] punto = new byte[65];
        punto[0] = 4;
        System.arraycopy(fijo(k.getW().getAffineX()), 0, punto, 1, 32);
        System.arraycopy(fijo(k.getW().getAffineY()), 0, punto, 33, 32);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(punto);
    }

    @Autowired AvisosRecordatorios avisos;

    private JsonNode ana;

    @BeforeEach
    void preparar() throws Exception {
        PUSH.clear();
        respuesta = PushEnvio.Resultado.ENVIADO;
        ana = persona("ana@correo.co");
        CORREOS.clear();
    }

    private JsonNode persona(String email) throws Exception {
        var r = mvc.perform(post("/api/v1/auth/registro-personal").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("nombre", "Persona", "email", email, "password", PASS)))).andReturn();
        assertThat(r.getResponse().getStatus()).isEqualTo(201);
        return cuerpo(r);
    }

    private ResultActions suscribir(JsonNode quien, String endpoint) throws Exception {
        return mvc.perform(post("/api/v1/push/suscripciones").header("Authorization", bearer(quien))
                .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("endpoint", endpoint))));
    }

    private void recordatorioParaHoy(String email) throws Exception {
        String exp = crearExpediente(ana, "E-" + UUID.randomUUID().toString().substring(0, 8));
        var u = jdbc.queryForMap("select id, tenant_id from usuarios where email = ?", email);
        jdbc.update("""
                insert into recordatorios (tenant_id, usuario_id, expediente_id, texto, estado, fecha, cita, clave)
                values (?, ?, ?, 'Control de glucosa', 'CONFIRMADO', ?, '{}'::jsonb, ?)""",
                u.get("tenant_id"), u.get("id"), UUID.fromString(exp), java.sql.Date.valueOf(LocalDate.now()),
                UUID.randomUUID().toString().replace("-", "").repeat(2));
    }

    private int suscripciones() {
        return jdbc.queryForObject("select count(*) from suscripciones_push", Integer.class);
    }

    // ---------- VAPID y destinos ----------

    @Test
    void laFirmaVapidSeVerificaConLaClavePublicaYSoloValeParaEseServicio() throws Exception {
        var ahora = Instant.parse("2026-11-25T12:00:00Z");
        String cabecera = new Vapid(PUBLICA, PRIVADA, "mailto:privacidad@ejemplo.co").autorizacion(URI.create(FCM), ahora);
        assertThat(cabecera).startsWith("vapid t=").endsWith(", k=" + PUBLICA);
        String[] jwt = cabecera.substring("vapid t=".length(), cabecera.indexOf(", k=")).split("\\.");
        var verificador = Signature.getInstance("SHA256withECDSAinP1363Format");
        verificador.initVerify(CLAVES.getPublic());
        verificador.update((jwt[0] + "." + jwt[1]).getBytes(StandardCharsets.US_ASCII));
        assertThat(verificador.verify(Base64.getUrlDecoder().decode(jwt[2]))).isTrue();
        JsonNode datos = json.readTree(Base64.getUrlDecoder().decode(jwt[1]));
        assertThat(datos.get("aud").asString()).isEqualTo("https://fcm.googleapis.com");
        assertThat(datos.get("exp").asLong(0)).isBetween(ahora.getEpochSecond() + 3600, ahora.getEpochSecond() + 86400);
        assertThat(datos.get("sub").asString()).isEqualTo("mailto:privacidad@ejemplo.co");
        assertThat(json.readTree(Base64.getUrlDecoder().decode(jwt[0])).get("alg").asString()).isEqualTo("ES256");
    }

    @ParameterizedTest
    @ValueSource(strings = {FCM, MOZILLA, "https://web.push.apple.com/QGb", "https://wns2-par02p.notify.windows.com/w/?token=x",
            "https://fcm.googleapis.com:443/fcm/send/x"})
    void seAdmitenLosServiciosDePushDeLosNavegadores(String endpoint) {
        assertThat(DestinoPush.permitido(endpoint)).isTrue();
    }

    @ParameterizedTest
    @ValueSource(strings = {"http://fcm.googleapis.com/x", "https://localhost/x", "https://127.0.0.1/x",
            "https://169.254.169.254/latest/meta-data", "https://agente:8000/internal/v1/ia", "https://evil.com/x",
            "https://fcm.googleapis.com.evil.com/x", "https://evilfcm.googleapis.com/x", "https://push.apple.com.evil.co/x",
            "https://user@fcm.googleapis.com/x", "https://fcm.googleapis.com:8443/x", "https://[::1]/x", "ftp://fcm.googleapis.com/x",
            "no es una url", ""})
    void seRechazaCualquierOtroDestino(String endpoint) {
        assertThat(DestinoPush.permitido(endpoint)).isFalse();
    }

    // ---------- suscribirse ----------

    @Test
    void laPersonaSeSuscribeVeElEstadoYSeDaDeBaja() throws Exception {
        mvc.perform(getAuth("/api/v1/push", ana)).andExpect(jsonPath("$.disponible").value(true))
                .andExpect(jsonPath("$.clave_publica").value(PUBLICA)).andExpect(jsonPath("$.dispositivos").value(0))
                .andExpect(jsonPath("$.por_correo").value(true));
        suscribir(ana, FCM).andExpect(status().isNoContent());
        suscribir(ana, FCM).andExpect(status().isNoContent()); // repetir no duplica
        assertThat(suscripciones()).isEqualTo(1);
        suscribir(ana, "https://evil.com/x").andExpect(status().isUnprocessableContent());
        mvc.perform(delete("/api/v1/push/suscripciones").header("Authorization", bearer(ana))
                .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("endpoint", FCM))))
                .andExpect(status().isNoContent());
        assertThat(suscripciones()).isZero();
    }

    @Test
    void unDispositivoPasaALaCuentaQueLoUsaAhoraYHayUnMaximo() throws Exception {
        JsonNode luis = persona("luis@correo.co");
        suscribir(ana, FCM).andExpect(status().isNoContent());
        suscribir(luis, FCM).andExpect(status().isNoContent());
        assertThat(jdbc.queryForObject("select u.email from suscripciones_push s join usuarios u on u.id = s.usuario_id",
                String.class)).isEqualTo("luis@correo.co");
        for (int i = 0; i < 10; i++) {
            suscribir(ana, FCM + "-" + i).andExpect(status().isNoContent());
        }
        suscribir(ana, FCM + "-11").andExpect(status().isConflict());
    }

    @Test
    void noSePuedeQuitarElCorreoSinNingunDispositivo() throws Exception {
        var sinCorreo = put("/api/v1/push/preferencia").header("Authorization", bearer(ana))
                .contentType(MediaType.APPLICATION_JSON).content("{\"por_correo\":false}");
        mvc.perform(sinCorreo).andExpect(status().isConflict());
        suscribir(ana, FCM).andExpect(status().isNoContent());
        mvc.perform(sinCorreo).andExpect(status().isNoContent());
        // al quitar el último dispositivo, el correo vuelve solo: no se queda sin avisos
        mvc.perform(delete("/api/v1/push/suscripciones").header("Authorization", bearer(ana))
                .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("endpoint", FCM))))
                .andExpect(status().isNoContent());
        mvc.perform(getAuth("/api/v1/push", ana)).andExpect(jsonPath("$.por_correo").value(true));
    }

    // ---------- avisos ----------

    @Test
    void elAvisoSaleAlDispositivoYAlCorreoYSeMarcaUnaVez() throws Exception {
        suscribir(ana, FCM).andExpect(status().isNoContent());
        recordatorioParaHoy("ana@correo.co");
        assertThat(avisos.enviarAvisos(LocalDate.now())).isEqualTo(1);
        assertThat(PUSH).containsExactly(FCM);
        assertThat(CORREOS).containsExactly("ana@correo.co");
        assertThat(avisos.enviarAvisos(LocalDate.now())).isZero();
    }

    @Test
    void sinCorreoSoloVaAlDispositivo() throws Exception {
        suscribir(ana, FCM).andExpect(status().isNoContent());
        jdbc.update("update usuarios set recordatorios_por_correo = false");
        recordatorioParaHoy("ana@correo.co");
        assertThat(avisos.enviarAvisos(LocalDate.now())).isEqualTo(1);
        assertThat(PUSH).containsExactly(FCM);
        assertThat(CORREOS).isEmpty();
    }

    @Test
    void siLaNotificacionNoLlegaSeAvisaPorCorreoYLaSuscripcionCaducadaSeBorra() throws Exception {
        suscribir(ana, FCM).andExpect(status().isNoContent());
        jdbc.update("update usuarios set recordatorios_por_correo = false");
        recordatorioParaHoy("ana@correo.co");
        respuesta = PushEnvio.Resultado.CADUCADA;
        assertThat(avisos.enviarAvisos(LocalDate.now())).isEqualTo(1);
        assertThat(CORREOS).containsExactly("ana@correo.co");
        assertThat(suscripciones()).isZero();
        assertThat(jdbc.queryForObject("select recordatorios_por_correo from usuarios where email='ana@correo.co'", Boolean.class))
                .isTrue();
    }

    @Test
    void borrarLaCuentaSeLlevaSusDispositivos() throws Exception {
        suscribir(ana, FCM).andExpect(status().isNoContent());
        mvc.perform(post("/api/v1/cuenta/eliminar").header("Authorization", bearer(ana))
                .contentType(MediaType.APPLICATION_JSON).content("{\"password\":\"" + PASS + "\"}"))
                .andExpect(status().isNoContent());
        assertThat(suscripciones()).isZero();
    }
}

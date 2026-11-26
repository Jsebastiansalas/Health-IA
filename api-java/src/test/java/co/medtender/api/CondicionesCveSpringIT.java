package co.medtender.api;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.web.servlet.error.BasicErrorController;
import org.springframework.context.ApplicationContext;
import org.springframework.core.annotation.AnnotatedElementUtils;
import org.springframework.http.HttpEntity;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.servlet.View;
import org.springframework.web.servlet.ViewResolver;
import org.springframework.web.servlet.function.support.RouterFunctionMapping;
import org.springframework.web.servlet.handler.AbstractUrlHandlerMapping;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping;
import org.springframework.web.servlet.resource.ResourceHttpRequestHandler;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Sostiene la excepción de {@code .trivyignore.yaml}: dos avisos de spring-webmvc 6.2.19 sin arreglo gratuito en
 * 6.2 que MedTender no cumple. Si alguna de estas pruebas falla, la aplicación empezó a usar la parte afectada:
 * <b>no se ajusta la prueba</b>; se quita la excepción o se migra a Spring 7.0.9 o posterior. Cuando la API use una
 * versión corregida, se borran esta clase y la excepción.
 *
 * <ul>
 *   <li>CVE-2026-47884: XsltView con una ruta «/**» que dibuja una vista sin nombre explícito.
 *       https://spring.io/security/cve-2026-47884</li>
 *   <li>CVE-2026-47890: fragmentos de vista enviados por eventos del servidor (SSE).
 *       https://spring.io/security/cve-2026-47890</li>
 * </ul>
 */
class CondicionesCveSpringIT extends IntegracionBase {

    private static final Pattern XSLT = Pattern.compile("Xslt|xslt|javax\\.xml\\.transform");
    private static final Pattern EVENTOS = Pattern.compile(
            "SseEmitter|ServerSentEvent|SseBuilder|ResponseBodyEmitter|FragmentsRendering|text/event-stream|TEXT_EVENT_STREAM|\\bFlux<");

    @Autowired private ApplicationContext contexto;

    /** CVE-2026-47884: nadie usa XsltView, ni como componente ni desde el código o la configuración. */
    @Test
    void noSeUsaXsltView() {
        var componentes = new ArrayList<Object>(contexto.getBeansOfType(View.class).values());
        componentes.addAll(contexto.getBeansOfType(ViewResolver.class).values());
        assertThat(componentes).extracting(c -> c.getClass().getName()).noneMatch(n -> XSLT.matcher(n).find());
        assertThat(enElCodigo(XSLT)).isEmpty();
    }

    /** CVE-2026-47884: ninguna ruta de la aplicación dibuja vistas (solo /error de Spring, que la nombra). */
    @Test
    void ningunaRutaPropiaDibujaVistas() {
        List<String> queDibujan = new ArrayList<>();
        for (var mapeo : contexto.getBeansOfType(RequestMappingHandlerMapping.class).values()) {
            mapeo.getHandlerMethods().forEach((ruta, h) -> {
                boolean devuelveCuerpo = AnnotatedElementUtils.hasAnnotation(h.getBeanType(), ResponseBody.class)
                        || h.hasMethodAnnotation(ResponseBody.class)
                        || HttpEntity.class.isAssignableFrom(h.getMethod().getReturnType());
                if (!devuelveCuerpo && !BasicErrorController.class.isAssignableFrom(h.getBeanType())) {
                    queDibujan.add(ruta + " -> " + h.getShortLogMessage());
                }
            });
        }
        assertThat(queDibujan).isEmpty();
        // Las rutas fuera de los controladores solo sirven archivos estáticos (sin vistas ni rutas «funcionales»).
        for (var mapeo : contexto.getBeansOfType(AbstractUrlHandlerMapping.class).values()) {
            assertThat(mapeo.getHandlerMap().values()).allMatch(m -> m instanceof ResourceHttpRequestHandler);
        }
        assertThat(contexto.getBeansOfType(RouterFunctionMapping.class).values()).allMatch(m -> m.getRouterFunction() == null);
    }

    /** CVE-2026-47890: no hay envíos de eventos del servidor ni de fragmentos de vista. */
    @Test
    void noSeEnvianEventosNiFragmentos() {
        for (var mapeo : contexto.getBeansOfType(RequestMappingHandlerMapping.class).values()) {
            mapeo.getHandlerMethods().forEach((ruta, h) -> {
                assertThat(h.getMethod().getGenericReturnType().getTypeName()).as(ruta.toString())
                        .doesNotContainPattern(EVENTOS);
                assertThat(ruta.getProducesCondition().toString()).as(ruta.toString()).doesNotContain("event-stream");
            });
        }
        assertThat(enElCodigo(EVENTOS)).isEmpty();
    }

    /** Archivos de la aplicación (código y configuración) donde aparece el patrón. */
    private static List<String> enElCodigo(Pattern patron) {
        try (Stream<Path> archivos = Files.walk(Path.of("src/main"))) {
            var todos = archivos.filter(Files::isRegularFile).toList();
            assertThat(todos).hasSizeGreaterThan(50); // si la ruta cambiara, la búsqueda no probaría nada
            return todos.stream().filter(f -> patron.matcher(leer(f)).find()).map(Path::toString).toList();
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    private static String leer(Path archivo) {
        try {
            return new String(Files.readAllBytes(archivo), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }
}

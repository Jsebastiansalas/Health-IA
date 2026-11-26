package co.medtender.api.errores;

import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.LoggerContext;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.classic.spi.ThrowableProxy;
import ch.qos.logback.core.AppenderBase;
import io.sentry.Sentry;
import io.sentry.SentryEvent;
import io.sentry.SentryLevel;
import io.sentry.protocol.SentryException;
import io.sentry.protocol.SentryStackFrame;
import io.sentry.protocol.SentryStackTrace;
import jakarta.annotation.PreDestroy;
import java.util.List;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Rastreo de errores (GlitchTip o compatible con Sentry) sin datos de salud. Reporta lo que se registra como
 * ERROR con excepcion (los 500 y las tareas programadas). El SDK no recoge nada por su cuenta y, ademas, cada
 * evento <b>se construye de nuevo solo con lo permitido</b>: tipo del error y clase, metodo y linea por donde
 * paso. Nunca mensajes, peticiones, usuarios ni contexto de registro. Sin {@code ERRORES_DSN} esta apagado.
 */
@Component
public class RastreoErrores {

    private static final String NOMBRE = "rastreo-errores";

    private final Appender appender;

    public RastreoErrores(@Value("${medtender.errores.dsn:}") String dsn, @Value("${medtender.entorno:desarrollo}") String entorno) {
        if (dsn == null || dsn.isBlank()) {
            this.appender = null;
            return;
        }
        Sentry.init(o -> {
            o.setDsn(dsn);
            o.setEnvironment(entorno);
            o.setEnableExternalConfiguration(false);
            o.setSendDefaultPii(false);
            o.setAttachServerName(false);
            o.setAttachStacktrace(false);
            o.setAttachThreads(false);
            o.setSendModules(false);
            o.setEnableUncaughtExceptionHandler(false);
            o.setEnableAutoSessionTracking(false);
            o.setSendClientReports(false);
            o.setMaxBreadcrumbs(0);
            o.setBeforeSend((evento, pista) -> limpiar(evento));
        });
        var contexto = (LoggerContext) LoggerFactory.getILoggerFactory();
        this.appender = new Appender();
        appender.setName(NOMBRE);
        appender.setContext(contexto);
        appender.start();
        contexto.getLogger(org.slf4j.Logger.ROOT_LOGGER_NAME).addAppender(appender);
    }

    /** Un evento nuevo con solo lo permitido; sin excepcion no se envia nada. */
    static SentryEvent limpiar(SentryEvent original) {
        List<SentryException> excepciones = original.getExceptions();
        if (excepciones == null || excepciones.isEmpty()) {
            return null;
        }
        var limpio = new SentryEvent(original.getTimestamp());
        limpio.setEventId(original.getEventId());
        limpio.setLevel(SentryLevel.ERROR);
        limpio.setPlatform("java");
        limpio.setEnvironment(original.getEnvironment());
        limpio.setRelease(original.getRelease());
        limpio.setSdk(original.getSdk());
        limpio.setServerName("api");
        limpio.setTag("servicio", "api");
        limpio.setExceptions(excepciones.stream().map(RastreoErrores::limpiar).toList());
        return limpio;
    }

    private static SentryException limpiar(SentryException original) {
        var e = new SentryException();
        e.setType(original.getType());
        e.setModule(original.getModule());
        e.setValue(""); // el mensaje puede traer texto de documentos, preguntas o nombres
        if (original.getStacktrace() != null && original.getStacktrace().getFrames() != null) {
            e.setStacktrace(new SentryStackTrace(original.getStacktrace().getFrames().stream().map(m -> {
                var marco = new SentryStackFrame();
                marco.setFilename(m.getFilename());
                marco.setModule(m.getModule());
                marco.setFunction(m.getFunction());
                marco.setLineno(m.getLineno());
                marco.setInApp(m.isInApp());
                return marco;
            }).toList()));
        }
        return e;
    }

    /** Envia lo pendiente (para las pruebas y el apagado). */
    void vaciar() {
        if (appender != null) {
            Sentry.flush(5000);
        }
    }

    @PreDestroy
    void apagar() {
        if (appender == null) {
            return;
        }
        var contexto = (LoggerContext) LoggerFactory.getILoggerFactory();
        contexto.getLogger(org.slf4j.Logger.ROOT_LOGGER_NAME).detachAppender(appender);
        appender.stop();
        Sentry.close();
    }

    /** Del registro solo se toma la excepcion, nunca el texto ni el contexto. */
    private static final class Appender extends AppenderBase<ILoggingEvent> {
        @Override
        protected void append(ILoggingEvent registro) {
            if (registro.getLevel().isGreaterOrEqual(Level.ERROR)
                    && registro.getThrowableProxy() instanceof ThrowableProxy proxy
                    && !registro.getLoggerName().startsWith("io.sentry")) {
                Sentry.captureException(proxy.getThrowable());
            }
        }
    }
}

package co.medtender.api.ingesta;

import java.util.Map;
import java.util.concurrent.ThreadPoolExecutor;
import org.slf4j.MDC;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

/** Ejecutor acotado para validar PDFs (antivirus + estructura) fuera de la peticion HTTP. */
@Configuration
@EnableAsync
public class AsyncConfig {

    public static final String EJECUTOR_VALIDACION = "ejecutorValidacion";

    @Bean(EJECUTOR_VALIDACION)
    ThreadPoolTaskExecutor ejecutorValidacion() {
        var ex = new ThreadPoolTaskExecutor();
        ex.setCorePoolSize(2);
        ex.setMaxPoolSize(4);
        ex.setQueueCapacity(100);
        ex.setThreadNamePrefix("validacion-");
        // Cola llena: se rechaza (el controlador responde 503) en vez de bloquear la peticion.
        ex.setRejectedExecutionHandler(new ThreadPoolExecutor.AbortPolicy());
        ex.setWaitForTasksToCompleteOnShutdown(true);
        ex.setAwaitTerminationSeconds(30);
        // Los logs de la tarea llevan el mismo request_id/usuario que la peticion que la origino.
        ex.setTaskDecorator(tarea -> {
            Map<String, String> contexto = MDC.getCopyOfContextMap();
            return () -> {
                if (contexto != null) {
                    MDC.setContextMap(contexto);
                }
                try {
                    tarea.run();
                } finally {
                    MDC.clear();
                }
            };
        });
        return ex;
    }
}

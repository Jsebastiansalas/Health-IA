package co.medtender.api.privacidad;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.beans.factory.DisposableBean;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.stereotype.Component;

/**
 * Envia por SMTP si hay un servidor configurado (SPRING_MAIL_HOST...). Sin servidor, NO envia nada: avisa en el
 * log que el correo no salio (y no escribe el enlace, que es una credencial de un solo uso). Asi un despliegue
 * sin SMTP falla de forma visible en lugar de callar.
 *
 * <p>El envío va en segundo plano: un servidor SMTP lento (5–6 s con Brevo) no hace esperar a quien cambia su
 * contraseña o activa la verificación en dos pasos. Si falla, queda en el log con el asunto (nunca el cuerpo).
 */
@Component
@ConditionalOnMissingBean(value = CorreoEnvio.class, ignored = CorreoEnvioPorDefecto.class)
public class CorreoEnvioPorDefecto implements CorreoEnvio, DisposableBean {

    private static final Logger log = LoggerFactory.getLogger(CorreoEnvioPorDefecto.class);

    private final ObjectProvider<JavaMailSender> smtp;
    private final String remitente;
    private final ThreadPoolTaskExecutor hilos = new ThreadPoolTaskExecutor();

    public CorreoEnvioPorDefecto(ObjectProvider<JavaMailSender> smtp,
                                 @Value("${medtender.correo.remitente:no-responder@medtender.local}") String remitente) {
        this.smtp = smtp;
        this.remitente = remitente;
        hilos.setCorePoolSize(1);
        hilos.setMaxPoolSize(2);
        hilos.setQueueCapacity(500);
        hilos.setThreadNamePrefix("correo-");
        hilos.setWaitForTasksToCompleteOnShutdown(true);
        hilos.setAwaitTerminationSeconds(20);
        hilos.initialize();
    }

    @Override
    public void destroy() {
        hilos.shutdown();
    }

    @Override
    public void enviar(String para, String asunto, String cuerpo) {
        JavaMailSender s = smtp.getIfAvailable();
        if (s == null) {
            log.warn("Correo NO enviado (no hay servidor SMTP configurado): asunto='{}'. Configura SPRING_MAIL_HOST.", asunto);
            return;
        }
        var m = new SimpleMailMessage();
        m.setFrom(remitente);
        m.setTo(para);
        m.setSubject(asunto);
        m.setText(cuerpo);
        try {
            hilos.execute(() -> {
                try {
                    s.send(m);
                } catch (RuntimeException e) {
                    log.error("No se pudo enviar el correo '{}': {}", asunto, e.getMessage());
                }
            });
        } catch (RuntimeException e) {
            log.error("Cola de correo llena; no se envió '{}'", asunto);
        }
    }
}

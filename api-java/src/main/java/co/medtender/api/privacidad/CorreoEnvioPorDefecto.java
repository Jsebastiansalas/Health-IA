package co.medtender.api.privacidad;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Component;

/**
 * Envia por SMTP si hay un servidor configurado (SPRING_MAIL_HOST...). Sin servidor, NO envia nada: avisa en el
 * log que el correo no salio (y no escribe el enlace, que es una credencial de un solo uso). Asi un despliegue
 * sin SMTP falla de forma visible en lugar de callar.
 */
@Component
@ConditionalOnMissingBean(value = CorreoEnvio.class, ignored = CorreoEnvioPorDefecto.class)
public class CorreoEnvioPorDefecto implements CorreoEnvio {

    private static final Logger log = LoggerFactory.getLogger(CorreoEnvioPorDefecto.class);

    private final ObjectProvider<JavaMailSender> smtp;
    private final String remitente;

    public CorreoEnvioPorDefecto(ObjectProvider<JavaMailSender> smtp,
                                 @Value("${medtender.correo.remitente:no-responder@medtender.local}") String remitente) {
        this.smtp = smtp;
        this.remitente = remitente;
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
        s.send(m);
    }
}

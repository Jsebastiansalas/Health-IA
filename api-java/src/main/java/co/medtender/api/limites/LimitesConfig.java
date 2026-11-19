package co.medtender.api.limites;

import co.medtender.api.config.MedtenderProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.core.StringRedisTemplate;

@Configuration
public class LimitesConfig {

    @Bean
    AlmacenLimites almacenLimites(MedtenderProperties props, StringRedisTemplate redis) {
        return "memoria".equals(props.rateLimit().backend()) ? new AlmacenMemoria() : new AlmacenRedis(redis);
    }
}

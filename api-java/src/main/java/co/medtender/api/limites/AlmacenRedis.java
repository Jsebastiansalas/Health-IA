package co.medtender.api.limites;

import java.util.List;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;

/** Ventana fija sobre Redis: SET NX EX + INCR + TTL en un unico script atomico. */
public class AlmacenRedis implements AlmacenLimites {

    @SuppressWarnings({"rawtypes", "unchecked"})
    private static final DefaultRedisScript<List> GOLPEAR = new DefaultRedisScript<>("""
            redis.call('SET', KEYS[1], 0, 'EX', ARGV[1], 'NX')
            local c = redis.call('INCR', KEYS[1])
            local t = redis.call('TTL', KEYS[1])
            return {c, t}
            """, List.class);

    private final StringRedisTemplate redis;

    public AlmacenRedis(StringRedisTemplate redis) {
        this.redis = redis;
    }

    @Override
    @SuppressWarnings("unchecked")
    public Conteo golpear(String clave, int ventanaS) {
        List<Long> r = (List<Long>) redis.execute(GOLPEAR, List.of(clave), Integer.toString(ventanaS));
        if (r == null || r.size() < 2) {
            throw new IllegalStateException("Respuesta vacia de Redis");
        }
        return new Conteo(r.get(0), (int) Math.max(1, r.get(1)));
    }

    @Override
    public Conteo contar(String clave) {
        String valor = redis.opsForValue().get(clave);
        if (valor == null) {
            return new Conteo(0, 0);
        }
        Long ttl = redis.getExpire(clave);
        return new Conteo(Long.parseLong(valor), (int) Math.max(1, ttl == null ? 1 : ttl));
    }

    @Override
    public void reiniciar() {
        var claves = redis.keys("rl:*");
        if (claves != null && !claves.isEmpty()) {
            redis.delete(claves);
        }
    }
}

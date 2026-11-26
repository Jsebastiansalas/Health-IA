package co.medtender.api.security;

import java.util.UUID;
import java.util.function.Supplier;

/**
 * Contexto de aislamiento de la hebra actual. {@link ContextoDataSource} lo copia a cada conexion
 * que toma del pool, y las politicas Row-Level Security de PostgreSQL (V8) deciden con el que filas
 * se ven.
 *
 * <p>Por defecto NO hay contexto: la hebra no ve ninguna fila. Se fija el tenant en la peticion
 * autenticada y el modo sistema solo en procesos que cruzan tenants por naturaleza (login, tareas
 * asincronas). Ambos se restauran al salir, nunca se "olvidan" abiertos.
 */
public final class ContextoTenant {

    /**
     * Tenant visible, si la hebra actua como proceso del sistema y, para un cuidador, el UNICO expediente
     * ajeno al que se limita la base mientras actua con el tenant de su dueña (V17).
     */
    public record Contexto(UUID tenantId, boolean sistema, UUID expedienteInvitado) {
        static final Contexto NINGUNO = new Contexto(null, false, null);
    }

    private static final ThreadLocal<Contexto> ACTUAL = ThreadLocal.withInitial(() -> Contexto.NINGUNO);

    private ContextoTenant() {}

    public static Contexto actual() {
        return ACTUAL.get();
    }

    /** Fija el tenant de la peticion. Lo limpia {@link ContextoTenantFilter} al terminarla. */
    public static void fijarTenant(UUID tenantId) {
        ACTUAL.set(new Contexto(tenantId, false, null));
    }

    /**
     * Lo que queda de la peticion es de un cuidador: tenant de la dueña, limitado a un expediente. Solo lo
     * llama {@code AutorizacionExpediente} tras comprobar la invitacion aceptada.
     */
    public static void entrarComoInvitado(UUID tenantDeLaDuena, UUID expedienteId) {
        ACTUAL.set(new Contexto(tenantDeLaDuena, false, expedienteId));
    }

    /** Lee o escribe lo de la propia cuenta (consentimiento, recordatorios) y restaura el contexto previo. */
    public static <T> T enLoPropio(UUID tenantId, Supplier<T> accion) {
        Contexto previo = ACTUAL.get();
        fijarTenant(tenantId);
        try {
            return accion.get();
        } finally {
            ACTUAL.set(previo);
        }
    }

    public static void limpiar() {
        ACTUAL.remove();
    }

    /** Ejecuta como proceso del sistema (ve todos los tenants) y restaura el contexto previo. */
    public static <T> T comoSistema(Supplier<T> accion) {
        Contexto previo = ACTUAL.get();
        ACTUAL.set(new Contexto(null, true, null));
        try {
            return accion.get();
        } finally {
            ACTUAL.set(previo);
        }
    }

    public static void comoSistema(Runnable accion) {
        comoSistema(() -> {
            accion.run();
            return null;
        });
    }
}

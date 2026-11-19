package co.medtender.api.limites;

public class LimiteExcedidoException extends RuntimeException {

    private final int reintentarEnS;

    public LimiteExcedidoException(int reintentarEnS) {
        super("Demasiadas solicitudes. Intente de nuevo en " + reintentarEnS + " s.");
        this.reintentarEnS = reintentarEnS;
    }

    public int getReintentarEnS() {
        return reintentarEnS;
    }
}

package co.medtender.api.domain;

public enum Permiso {
    LECTOR(1),
    EDITOR(2),
    ADMIN(3);

    private final int nivel;

    Permiso(int nivel) {
        this.nivel = nivel;
    }

    public int nivel() {
        return nivel;
    }
}

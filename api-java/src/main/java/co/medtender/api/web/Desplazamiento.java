package co.medtender.api.web;

import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;

/** Paginacion por limite y desplazamiento arbitrario (offset/limit), como la API anterior. */
public record Desplazamiento(long desplazamiento, int limite) implements Pageable {

    public static Desplazamiento de(int offset, int limit) {
        return new Desplazamiento(offset, limit);
    }

    @Override public boolean isPaged() { return true; }
    @Override public int getPageNumber() { return (int) (desplazamiento / limite); }
    @Override public int getPageSize() { return limite; }
    @Override public long getOffset() { return desplazamiento; }
    @Override public Sort getSort() { return Sort.unsorted(); }
    @Override public Pageable next() { return new Desplazamiento(desplazamiento + limite, limite); }
    @Override public Pageable previousOrFirst() { return new Desplazamiento(Math.max(0, desplazamiento - limite), limite); }
    @Override public Pageable first() { return new Desplazamiento(0, limite); }
    @Override public Pageable withPage(int pageNumber) { return new Desplazamiento((long) pageNumber * limite, limite); }
    @Override public boolean hasPrevious() { return desplazamiento > 0; }
}

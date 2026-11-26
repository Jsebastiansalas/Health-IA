-- Cuánto conserva cada cuenta su historial de preguntas y respuestas. NULL: no se borra solo.
ALTER TABLE tenants ADD COLUMN retencion_historial_meses INT
    CONSTRAINT tenants_retencion_valida CHECK (retencion_historial_meses IN (3, 6, 12, 24));

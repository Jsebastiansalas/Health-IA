-- Línea de tiempo por documento (sprint 44).
--
-- Lo que el modelo propone al leer UN documento (eventos con fecha y valores de laboratorio), para no volver a
-- preguntarle cada vez que se abre la línea de tiempo ni cortar los expedientes largos. Son propuestas SIN
-- comprobar: el agente las valida contra el texto literal cada vez que arma la línea.
-- Es contenido de salud: `datos` se guarda cifrado con DATOS_CLAVE (mismo formato que `consultas.respuesta`).
CREATE TABLE extracciones_linea (
    documento_id UUID PRIMARY KEY REFERENCES documentos(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    expediente_id UUID NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    -- Huella de las instrucciones al modelo: si cambian, lo guardado deja de valer.
    version CHAR(32) NOT NULL,
    -- Huella de los fragmentos leídos: si cambian, también.
    huella_fragmentos CHAR(64) NOT NULL,
    datos JSONB NOT NULL,
    modelo_llm VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_extracciones_linea_expediente ON extracciones_linea (tenant_id, expediente_id);

ALTER TABLE extracciones_linea ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracciones_linea FORCE ROW LEVEL SECURITY;
CREATE POLICY aislamiento_tenant ON extracciones_linea
    USING (app_sistema() OR tenant_id = app_tenant())
    WITH CHECK (app_sistema() OR tenant_id = app_tenant());

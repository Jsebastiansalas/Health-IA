-- Cuentas personales (pacientes y familias) y consentimiento informado.
--
-- Un tenant PERSONAL es una persona con su propio espacio: un solo usuario y borrado inmediato del PDF.
-- El consentimiento deja constancia de que la persona sabe que sus documentos de salud se procesan con un
-- proveedor de IA externo (con anonimizacion previa) y de que puede borrar su historial y su cuenta.

ALTER TABLE tenants
    ADD COLUMN tipo VARCHAR(20) NOT NULL DEFAULT 'ORGANIZACION'
        CHECK (tipo IN ('ORGANIZACION', 'PERSONAL'));

CREATE TABLE consentimientos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    -- Version del texto aceptado: si cambia el texto, hay que aceptarlo de nuevo.
    version VARCHAR(30) NOT NULL,
    aceptado_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (usuario_id, version)
);
CREATE INDEX idx_consentimientos_tenant ON consentimientos (tenant_id, usuario_id);

-- Aislamiento por tenant (mismo patron que V8). La prueba de la suite que recorre las tablas con
-- tenant_id fallaria si faltara.
ALTER TABLE consentimientos ENABLE ROW LEVEL SECURITY;
ALTER TABLE consentimientos FORCE ROW LEVEL SECURITY;
CREATE POLICY aislamiento_tenant ON consentimientos
    USING (app_sistema() OR tenant_id = app_tenant())
    WITH CHECK (app_sistema() OR tenant_id = app_tenant());

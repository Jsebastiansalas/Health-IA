-- Recordatorios de controles (sprint 39).
--
-- El agente propone, a partir de lo que escriben los documentos («control en 3 meses», «cita el 12/02»), un
-- recordatorio con su cita; la persona lo CONFIRMA (y puede cambiar la fecha) antes de que exista un aviso.
-- Nunca hay recordatorios de tomas de medicamentos. El aviso por correo no repite datos de salud: solo la fecha.
-- Son de cada usuario (no del expediente): la API filtra por usuario_id y la base aísla por tenant.
CREATE TABLE recordatorios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    expediente_id UUID NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    texto VARCHAR(300) NOT NULL,
    fecha_texto VARCHAR(120) NOT NULL DEFAULT '',
    fecha_documento DATE,
    fecha_propuesta DATE,
    fecha DATE,
    estado VARCHAR(20) NOT NULL DEFAULT 'PROPUESTO'
        CHECK (estado IN ('PROPUESTO', 'CONFIRMADO', 'HECHO', 'DESCARTADO')),
    cita JSONB NOT NULL,
    -- Huella de (texto, documento, fecha escrita): la misma propuesta no se repite al volver a buscar.
    clave CHAR(64) NOT NULL,
    aviso_enviado_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT recordatorio_confirmado_con_fecha CHECK (estado <> 'CONFIRMADO' OR fecha IS NOT NULL),
    CONSTRAINT recordatorio_unico UNIQUE (usuario_id, expediente_id, clave)
);
CREATE INDEX idx_recordatorios_usuario ON recordatorios (usuario_id, estado, fecha);
CREATE INDEX idx_recordatorios_avisos ON recordatorios (fecha) WHERE estado = 'CONFIRMADO' AND aviso_enviado_at IS NULL;

ALTER TABLE recordatorios ENABLE ROW LEVEL SECURITY;
ALTER TABLE recordatorios FORCE ROW LEVEL SECURITY;
CREATE POLICY aislamiento_tenant ON recordatorios
    USING (app_sistema() OR tenant_id = app_tenant())
    WITH CHECK (app_sistema() OR tenant_id = app_tenant());

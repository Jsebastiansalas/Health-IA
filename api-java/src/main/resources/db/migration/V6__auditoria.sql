-- Auditoria de accesos (registro de solo anexado). Sin claves foraneas a proposito: el registro
-- debe sobrevivir a la eliminacion de expedientes o usuarios y no puede bloquearla. Un trigger
-- rechaza UPDATE y DELETE; solo se puede insertar. (TRUNCATE no activa triggers de fila: queda
-- reservado a quien administra la base de datos.)
CREATE TABLE auditoria (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID,
    usuario_id UUID,
    email VARCHAR(150),
    accion VARCHAR(40) NOT NULL,
    resultado VARCHAR(12) NOT NULL CHECK (resultado IN ('OK', 'DENEGADO', 'ERROR')),
    recurso_tipo VARCHAR(30),
    recurso_id UUID,
    ip VARCHAR(64),
    request_id VARCHAR(64),
    detalle JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_auditoria_tenant ON auditoria (tenant_id, created_at DESC);
CREATE INDEX idx_auditoria_usuario ON auditoria (usuario_id, created_at DESC);
CREATE INDEX idx_auditoria_recurso ON auditoria (recurso_id, created_at DESC);
CREATE INDEX idx_auditoria_accion ON auditoria (accion, created_at DESC);

CREATE FUNCTION auditoria_solo_anexar() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'La tabla auditoria es de solo anexado (% no permitido)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auditoria_inmutable BEFORE UPDATE OR DELETE ON auditoria
FOR EACH ROW EXECUTE FUNCTION auditoria_solo_anexar();

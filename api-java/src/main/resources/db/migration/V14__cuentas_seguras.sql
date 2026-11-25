-- Cuentas seguras (sprint 40): sesiones revocables, restablecer contraseña y verificación en dos pasos.

-- 1) Sesiones. Cada token de renovación (refresh) tiene una fila con el hash de su identificador (jti). Al
--    renovar se ROTA: la fila se marca usada y nace otra de la misma familia. Si alguien presenta un token ya
--    usado, alguien lo copió: se revoca toda la familia (todas las renovaciones de ese inicio de sesión).
CREATE TABLE sesiones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    familia UUID NOT NULL,
    jti_hash CHAR(64) NOT NULL UNIQUE,
    expira_at TIMESTAMPTZ NOT NULL,
    usado_at TIMESTAMPTZ,
    revocada_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_sesiones_familia ON sesiones (familia);
CREATE INDEX idx_sesiones_usuario ON sesiones (usuario_id) WHERE revocada_at IS NULL;

-- Los access tokens no tienen estado (30 min). Al cambiar o restablecer la contraseña, o al «cerrar todas las
-- sesiones», se mueve esta fecha y se rechaza cualquier token emitido antes (ya se consulta el usuario en cada
-- petición, así que no cuesta nada más).
ALTER TABLE usuarios ADD COLUMN sesiones_validas_desde TIMESTAMPTZ NOT NULL DEFAULT TO_TIMESTAMP(0);

-- 2) Restablecer la contraseña: enlace de un solo uso por correo (30 min). Solo se guarda el hash del token.
CREATE TABLE restablecimientos_clave (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    expira_at TIMESTAMPTZ NOT NULL,
    usado_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_restablecimientos_usuario ON restablecimientos_clave (usuario_id);

-- 3) Verificación en dos pasos (TOTP, RFC 6238). El secreto va cifrado (AES-GCM, clave fuera de la base);
--    los códigos de respaldo, solo como hash y de un solo uso.
ALTER TABLE usuarios ADD COLUMN totp_secreto TEXT;
ALTER TABLE usuarios ADD COLUMN totp_pendiente TEXT;
ALTER TABLE usuarios ADD COLUMN totp_activo BOOLEAN NOT NULL DEFAULT FALSE;
CREATE TABLE codigos_respaldo (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    codigo_hash CHAR(64) NOT NULL,
    usado_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_codigos_respaldo_usuario ON codigos_respaldo (usuario_id) WHERE usado_at IS NULL;

ALTER TABLE sesiones ENABLE ROW LEVEL SECURITY;
ALTER TABLE sesiones FORCE ROW LEVEL SECURITY;
CREATE POLICY aislamiento_tenant ON sesiones
    USING (app_sistema() OR tenant_id = app_tenant())
    WITH CHECK (app_sistema() OR tenant_id = app_tenant());

ALTER TABLE restablecimientos_clave ENABLE ROW LEVEL SECURITY;
ALTER TABLE restablecimientos_clave FORCE ROW LEVEL SECURITY;
CREATE POLICY aislamiento_tenant ON restablecimientos_clave
    USING (app_sistema() OR tenant_id = app_tenant())
    WITH CHECK (app_sistema() OR tenant_id = app_tenant());

ALTER TABLE codigos_respaldo ENABLE ROW LEVEL SECURITY;
ALTER TABLE codigos_respaldo FORCE ROW LEVEL SECURITY;
CREATE POLICY aislamiento_tenant ON codigos_respaldo
    USING (app_sistema() OR tenant_id = app_tenant())
    WITH CHECK (app_sistema() OR tenant_id = app_tenant());

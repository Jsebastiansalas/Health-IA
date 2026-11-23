-- Verificacion de correo de las cuentas personales (sprint 33).
--
-- Una cuenta personal puede registrarse sin pagar nada ni hablar con nadie: sin confirmar que el correo es de
-- quien se registra, cualquiera podria crear cuentas en masa y gastar el modelo de IA. El token que se envia
-- por correo no se guarda: solo su SHA-256, asi que una filtracion de la base no permite verificar cuentas.
-- Un usuario esta verificado si tiene alguna fila con usado_at.
CREATE TABLE verificaciones_correo (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    expira_at TIMESTAMPTZ NOT NULL,
    usado_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_verificaciones_usuario ON verificaciones_correo (usuario_id);

ALTER TABLE verificaciones_correo ENABLE ROW LEVEL SECURITY;
ALTER TABLE verificaciones_correo FORCE ROW LEVEL SECURITY;
CREATE POLICY aislamiento_tenant ON verificaciones_correo
    USING (app_sistema() OR tenant_id = app_tenant())
    WITH CHECK (app_sistema() OR tenant_id = app_tenant());

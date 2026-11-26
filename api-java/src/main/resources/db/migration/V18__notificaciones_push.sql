-- Notificaciones push de la app instalada (sprint 45).
--
-- Solo se guarda la dirección que el servicio de push del navegador da al dispositivo. Las notificaciones van
-- SIN contenido (el texto neutro lo pone la aplicación en el teléfono), así que no hacen falta las claves de
-- cifrado de la suscripción ni viaja ningún dato de salud.
CREATE TABLE suscripciones_push (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    endpoint VARCHAR(1000) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_suscripciones_push_usuario ON suscripciones_push (usuario_id);

ALTER TABLE suscripciones_push ENABLE ROW LEVEL SECURITY;
ALTER TABLE suscripciones_push FORCE ROW LEVEL SECURITY;
CREATE POLICY aislamiento_tenant ON suscripciones_push
    USING (app_sistema() OR tenant_id = app_tenant())
    WITH CHECK (app_sistema() OR tenant_id = app_tenant());
CREATE POLICY nada_de_la_cuenta ON suscripciones_push AS RESTRICTIVE USING (app_invitado() IS NULL);

-- Quien activa las notificaciones puede dejar de recibir el correo del recordatorio.
ALTER TABLE usuarios ADD COLUMN recordatorios_por_correo BOOLEAN NOT NULL DEFAULT TRUE;

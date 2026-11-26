-- Cuidadores (sprint 45): una persona comparte UN expediente por invitación de correo.
--
-- Cada cuenta personal es su propio tenant, así que el cuidador necesita ver filas de otro tenant. La API
-- solo lo permite en los endpoints que lo piden de forma expresa y, durante esa petición, actúa con el tenant
-- de la dueña ADEMÁS de `app.expediente_invitado`. Las políticas RESTRICTIVAS de abajo se suman (AND) a las
-- de aislamiento: aunque la API se equivocara, la base solo entrega ese expediente.
CREATE TABLE comparticiones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),                 -- el de la dueña
    expediente_id UUID NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    invitado_por UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    correo_invitado VARCHAR(150) NOT NULL,                          -- en minúsculas
    permiso VARCHAR(10) NOT NULL CHECK (permiso IN ('LECTOR', 'EDITOR')),
    estado VARCHAR(10) NOT NULL DEFAULT 'PENDIENTE' CHECK (estado IN ('PENDIENTE', 'ACEPTADA', 'REVOCADA')),
    token_hash CHAR(64) NOT NULL UNIQUE,                            -- nunca el enlace
    expira_at TIMESTAMPTZ NOT NULL,
    invitado_usuario_id UUID REFERENCES usuarios(id) ON DELETE CASCADE,
    invitado_tenant_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    aceptada_at TIMESTAMPTZ,
    ultimo_acceso_at TIMESTAMPTZ,
    revocada_at TIMESTAMPTZ,
    CONSTRAINT comparticion_aceptada_con_persona
        CHECK (estado <> 'ACEPTADA' OR (invitado_usuario_id IS NOT NULL AND invitado_tenant_id IS NOT NULL))
);
CREATE INDEX idx_comparticiones_expediente ON comparticiones (tenant_id, expediente_id);
CREATE INDEX idx_comparticiones_invitado ON comparticiones (invitado_usuario_id) WHERE estado = 'ACEPTADA';
CREATE UNIQUE INDEX comparticion_una_vigente ON comparticiones (expediente_id, correo_invitado)
    WHERE estado <> 'REVOCADA';

ALTER TABLE comparticiones ENABLE ROW LEVEL SECURITY;
ALTER TABLE comparticiones FORCE ROW LEVEL SECURITY;
CREATE POLICY aislamiento_tenant ON comparticiones
    USING (app_sistema() OR tenant_id = app_tenant())
    WITH CHECK (app_sistema() OR tenant_id = app_tenant());
-- El cuidador puede LEER las suyas (así la API sabe a qué tiene acceso); no cambiarlas.
CREATE POLICY lectura_del_invitado ON comparticiones FOR SELECT
    USING (invitado_tenant_id = app_tenant());

CREATE OR REPLACE FUNCTION app_invitado() RETURNS uuid
    LANGUAGE sql STABLE PARALLEL SAFE
    AS $$ SELECT nullif(current_setting('app.expediente_invitado', true), '')::uuid $$;

-- Con `app.expediente_invitado` puesto, de lo que cuelga de un expediente solo existe ese expediente.
CREATE POLICY solo_el_expediente_compartido ON expedientes AS RESTRICTIVE
    USING (app_invitado() IS NULL OR id = app_invitado());

DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['documentos', 'fragmentos', 'consultas', 'reindexaciones', 'expediente_permisos',
                             'recordatorios', 'extracciones_linea']
    LOOP
        EXECUTE format('CREATE POLICY solo_el_expediente_compartido ON %I AS RESTRICTIVE '
                       'USING (app_invitado() IS NULL OR expediente_id = app_invitado())', t);
    END LOOP;
    -- Y de la cuenta de la dueña no existe nada.
    FOREACH t IN ARRAY ARRAY['usuarios', 'tenants', 'consentimientos', 'verificaciones_correo', 'sesiones',
                             'restablecimientos_clave', 'codigos_respaldo', 'comparticiones']
    LOOP
        EXECUTE format('CREATE POLICY nada_de_la_cuenta ON %I AS RESTRICTIVE USING (app_invitado() IS NULL)', t);
    END LOOP;
END
$$;

-- La auditoría se puede anotar (queda en el registro de la dueña), pero no leer.
CREATE POLICY nada_de_la_cuenta ON auditoria AS RESTRICTIVE FOR SELECT USING (app_invitado() IS NULL);
CREATE POLICY solo_el_expediente_compartido ON actas_purga AS RESTRICTIVE FOR SELECT
    USING (app_invitado() IS NULL OR documento_id IN (SELECT id FROM documentos));

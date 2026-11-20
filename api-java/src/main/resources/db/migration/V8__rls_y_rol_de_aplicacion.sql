-- Aislamiento de tenants EN la base de datos (Row-Level Security).
--
-- Hasta ahora cada consulta filtraba por tenant_id a mano. Si alguien escribia una consulta nueva
-- sin ese filtro, la base entregaba filas de otra organizacion. Desde esta migracion la base
-- tambien lo impide: cada conexion declara en quien actua y solo ve sus filas.
--
-- Contexto de la conexion (lo fijan la API Java y el agente al tomar una conexion / abrir una
-- transaccion):
--   app.tenant_id  UUID del tenant de la peticion en curso.
--   app.sistema    'on' solo en procesos del sistema que, por naturaleza, cruzan tenants: el login
--                  (busca al usuario por correo), el worker de procesamiento y el barrido de purga.
-- Sin ninguno de los dos, la conexion NO ve ninguna fila (denegado por defecto).
--
-- Las politicas NO protegen contra un superusuario ni contra quien tenga BYPASSRLS. Por eso la
-- aplicacion se conecta con el rol `medtender_app` (sin esos privilegios) y las migraciones con
-- el rol propietario del esquema.

-- ---------------------------------------------------------------------------------------------
-- Rol de la aplicacion
-- ---------------------------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'medtender_app') THEN
        CREATE ROLE medtender_app LOGIN PASSWORD '${app_password}'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    ELSE
        ALTER ROLE medtender_app PASSWORD '${app_password}'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO medtender_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO medtender_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO medtender_app;
-- Tablas futuras creadas por el propietario (migraciones nuevas) quedan accesibles sin repetir esto.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO medtender_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO medtender_app;

-- ---------------------------------------------------------------------------------------------
-- Funciones de contexto
-- ---------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app_tenant() RETURNS uuid
    LANGUAGE sql STABLE PARALLEL SAFE
    AS $$ SELECT nullif(current_setting('app.tenant_id', true), '')::uuid $$;

CREATE OR REPLACE FUNCTION app_sistema() RETURNS boolean
    LANGUAGE sql STABLE PARALLEL SAFE
    AS $$ SELECT coalesce(current_setting('app.sistema', true), '') = 'on' $$;

-- ---------------------------------------------------------------------------------------------
-- Politicas
-- ---------------------------------------------------------------------------------------------
-- Tablas cuyo tenant_id es obligatorio: se ve y se escribe solo lo del propio tenant.
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['usuarios', 'expedientes', 'expediente_permisos', 'documentos',
                             'fragmentos', 'reindexaciones', 'consultas']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY aislamiento_tenant ON %I USING (app_sistema() OR tenant_id = app_tenant()) '
            'WITH CHECK (app_sistema() OR tenant_id = app_tenant())', t);
    END LOOP;
END
$$;

-- tenants: la fila de cada organizacion es la suya.
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY aislamiento_tenant ON tenants
    USING (app_sistema() OR id = app_tenant())
    WITH CHECK (app_sistema() OR id = app_tenant());

-- Auditoria y actas de purga: tenant_id puede ser NULL (login fallido, documento huerfano).
-- Cualquiera puede ESCRIBIR eventos sin tenant, pero solo se LEEN los del propio tenant.
ALTER TABLE auditoria ENABLE ROW LEVEL SECURITY;
ALTER TABLE auditoria FORCE ROW LEVEL SECURITY;
CREATE POLICY aislamiento_tenant ON auditoria
    USING (app_sistema() OR tenant_id = app_tenant())
    WITH CHECK (app_sistema() OR tenant_id IS NULL OR tenant_id = app_tenant());

ALTER TABLE actas_purga ENABLE ROW LEVEL SECURITY;
ALTER TABLE actas_purga FORCE ROW LEVEL SECURITY;
CREATE POLICY aislamiento_tenant ON actas_purga
    USING (app_sistema() OR tenant_id = app_tenant())
    WITH CHECK (app_sistema() OR tenant_id IS NULL OR tenant_id = app_tenant());

-- fragmentos_reindex no lleva tenant_id: hereda el de su reindexacion (que tambien esta protegida).
ALTER TABLE fragmentos_reindex ENABLE ROW LEVEL SECURITY;
ALTER TABLE fragmentos_reindex FORCE ROW LEVEL SECURITY;
CREATE POLICY aislamiento_tenant ON fragmentos_reindex
    USING (app_sistema() OR reindexacion_id IN (SELECT id FROM reindexaciones))
    WITH CHECK (app_sistema() OR reindexacion_id IN (SELECT id FROM reindexaciones));

-- med_cum, med_precio y med_carga son datos PUBLICOS de INVIMA (sin tenant_id): no llevan politica.

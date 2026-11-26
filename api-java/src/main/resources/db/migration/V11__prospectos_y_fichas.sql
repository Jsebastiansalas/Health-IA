-- Sprint 28: informacion de medicamentos con fuente.
-- 1) El prospecto que sube la persona es un tipo de documento mas (entra al mismo RAG, con citas).
ALTER TABLE documentos DROP CONSTRAINT IF EXISTS documentos_tipo_documento_check;
ALTER TABLE documentos ADD CONSTRAINT documentos_tipo_documento_check
    CHECK (tipo_documento IN ('PLIEGO', 'ADENDA', 'FICHA_TECNICA', 'REGISTRO_SANITARIO',
                              'HISTORIA_CLINICA', 'PRESUPUESTO', 'PROSPECTO'));

-- 2) Fichas tecnicas oficiales (secciones de contraindicaciones, advertencias, interacciones, embarazo y
--    reacciones adversas; nunca posologia) cargadas desde una fuente abierta, con su enlace de origen.
--    Son datos PUBLICOS (sin tenant_id), como med_cum: no llevan politica de RLS.
CREATE TABLE med_ficha (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fuente          VARCHAR(10)  NOT NULL CHECK (fuente IN ('CIMA')),
    nregistro       VARCHAR(20)  NOT NULL,
    medicamento     VARCHAR(300) NOT NULL,
    principio_activo VARCHAR(200) NOT NULL,
    principio_norm  VARCHAR(200) NOT NULL,
    seccion         VARCHAR(8)   NOT NULL,
    titulo          VARCHAR(200) NOT NULL,
    texto           TEXT         NOT NULL,
    url_origen      VARCHAR(400) NOT NULL,
    cargado_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (fuente, nregistro, seccion)
);
CREATE INDEX idx_med_ficha_principio ON med_ficha (principio_norm);

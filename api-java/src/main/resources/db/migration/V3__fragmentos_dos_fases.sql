-- Los fragmentos se guardan antes de vectorizar (embedding NULL hasta terminar la vectorizacion).
-- La verificacion previa a la purga cuenta COUNT(fragmentos WHERE embedding IS NOT NULL). Un
-- documento solo es consultable en INDEXADO_*, asi que los fragmentos sin vector nunca llegan a
-- una busqueda.
ALTER TABLE fragmentos ALTER COLUMN embedding DROP NOT NULL;
ALTER TABLE documentos ALTER COLUMN extractor_version SET DEFAULT 'pdfium-pdfplumber-v1';

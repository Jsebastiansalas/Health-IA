-- Fotos y escaneos ademas de PDF: el documento recuerda en que formato llego para que el agente sepa
-- como leerlo (extraccion de PDF o OCR de imagen). Los existentes son PDF.
ALTER TABLE documentos
    ADD COLUMN formato VARCHAR(10) NOT NULL DEFAULT 'PDF'
        CHECK (formato IN ('PDF', 'JPG', 'PNG', 'HEIC'));

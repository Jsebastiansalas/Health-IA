// Contratos de la API MedTender (API Java en api-java/ y agente/app/rag/motor.py).

export type RolGlobal = "ADMIN_TENANT" | "JURIDICO" | "AUDITOR_MEDICO" | "BIOMEDICO" | "LECTOR";
export type Permiso = "LECTOR" | "EDITOR" | "ADMIN";
export type TipoExpediente = "LICITACION_MEDICAMENTOS" | "DOTACION_BIOMEDICA" | "AUDITORIA_CLINICA";
export type TipoDocumento =
  | "PLIEGO"
  | "ADENDA"
  | "FICHA_TECNICA"
  | "REGISTRO_SANITARIO"
  | "HISTORIA_CLINICA"
  | "PRESUPUESTO";
export type EstadoIndexacion =
  | "RECIBIDO"
  | "VALIDANDO"
  | "EN_COLA"
  | "EXTRAYENDO_OCR"
  | "FRAGMENTANDO"
  | "VECTORIZANDO"
  | "INDEXADO_PENDIENTE_PURGA"
  | "INDEXADO_Y_PURGADO"
  | "ERROR_PURGADO";

export interface Tokens {
  access_token: string;
  refresh_token: string;
}

export interface Usuario {
  id: string;
  tenant_id: string;
  email: string;
  nombre_completo: string;
  rol_global: RolGlobal;
  activo: boolean;
}

export interface Expediente {
  id: string;
  codigo_expediente: string;
  titulo: string;
  entidad_contratante: string | null;
  tipo_expediente: TipoExpediente;
  estado: "ABIERTO" | "CERRADO" | "ARCHIVADO";
  embedding_model_activo: string;
  embedding_dimension: number;
  created_at: string;
  mi_permiso: Permiso | null;
}

export interface ActaPurga {
  id: string;
  motivo: string;
  sha256_original: string | null;
  chunks_esperados: number | null;
  chunks_verificados: number | null;
  archivo_existia: boolean;
  detalle: string | null;
  purged_at: string;
}

export interface Documento {
  id: string;
  expediente_id: string;
  nombre_archivo_original: string;
  tipo_documento: TipoDocumento;
  numero_adenda: number | null;
  sha256_original: string;
  tamano_bytes: number;
  total_paginas: number | null;
  estado_indexacion: EstadoIndexacion;
  motivo_error: string | null;
  embedding_model: string;
  ocr_version: string;
  total_chunks_esperados: number | null;
  total_chunks_guardados: number | null;
  temp_file_purged: boolean;
  uploaded_at: string;
  purged_at: string | null;
  purga_programada_at: string | null;
  paginas_ocr: number;
  progreso: number;
  aviso_ocr_desactualizado: boolean;
  actas_purga?: ActaPurga[];
}

export interface Cita {
  documentoId: string;
  nombreArchivo: string;
  tipoDocumento: TipoDocumento;
  numeroAdenda: number;
  sha256Original: string;
  paginaInicio: number;
  paginaFin: number;
  seccion: string;
  orden: number;
  extractoLiteral: string;
  extractoAjustado: boolean;
  metodoExtraccion: "NATIVE" | "OCR" | "MIXED";
  confianzaOcr: number | null;
  requiereVerificacionVisualOriginal: boolean;
  motivoVerificacionVisual: string | null;
}

export interface RespuestaConsulta {
  consultaId: string;
  pregunta?: string;
  createdAt?: string;
  respuestaAnalitica: string;
  sinEvidencia: boolean;
  alertas: string[];
  citas: Cita[];
  modeloEmbeddings: string;
  modeloLlm: string | null;
  fragmentosRecuperados: number;
  latenciaMs: number;
}

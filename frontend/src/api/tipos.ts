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
  | "PRESUPUESTO"
  | "PROSPECTO";
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

export type FormatoDocumento = "PDF" | "JPG" | "PNG" | "HEIC";

export interface Documento {
  id: string;
  /** Formato real del archivo; ausente en respuestas anteriores al sprint 26 (son PDF). */
  formato?: FormatoDocumento;
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
  /** Qué tiene el fragmento que el texto extraído no garantiza. Ausente en consultas guardadas antes del sprint 16. */
  tiposEvidencia?: TipoEvidencia[];
}

export type TipoEvidencia = "FIRMA_O_SELLO" | "TABLA" | "IMAGEN" | "OCR" | "OCR_BAJA_CONFIANZA";

/** Aviso que el agente antepone cuando la pregunta describe una posible emergencia. */
export interface Urgencia {
  codigo: string;
  mensaje: string;
}

export interface EstadoConsentimiento {
  version: string;
  requerido: boolean;
  aceptado: boolean;
  aceptado_at: string | null;
  tipo_cuenta: "ORGANIZACION" | "PERSONAL";
  /** Las cuentas personales deben confirmar su correo (si el servidor lo exige). */
  correo_requerido: boolean;
  correo_verificado: boolean;
}

export interface RespuestaConsulta {
  consultaId: string;
  urgencia?: Urgencia | null;
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
  /** El asistente no decide dosis, qué tomar ni diagnósticos: respuesta fija que remite al médico. */
  limiteClinico?: { codigo: "dosis" | "receta" | "diagnostico" } | null;
  /** «Explícame este documento»: las consultas de ese modo traen además estos campos. */
  modo?: "explicar" | "cruce" | "cronologia" | "preparacion";
  documentoId?: string;
  deQueTrata?: string;
  hallazgos?: HallazgoExplicado[];
  terminos?: TerminoExplicado[];
  /** Estado del glosario curado de la capa «qué significan»: `revisado` es falso hasta que un profesional lo revise. */
  glosario?: { revisado: boolean; revision: string; terminos: number };
  senalesDeAlarma?: string[];
  preguntasParaElMedico?: string[];
  avisoGeneral?: string;
  /** «Advertencias de mis medicamentos» (modo cruce). */
  medicamentos?: { nombre: string; principio_activo?: string; cita: number; ficha?: boolean }[];
  diagnosticos?: { texto: string; cita: number }[];
  alergias?: { texto: string; cita: number }[];
  advertencias?: AdvertenciaCruzada[];
  sinFicha?: string[];
  fichas?: CitaFicha[];
  fuentesOficiales?: FuenteOficial[];
  /** «Mi línea de tiempo» (modo cronologia). */
  eventos?: EventoClinico[];
  analitos?: Analito[];
  /** La línea guardada se devolvió sin llamar al modelo porque los documentos no cambiaron. */
  guardada?: boolean;
  generadaAt?: string;
  /** «Preparar mi cita» (modo preparacion). */
  cambios?: CambioAnalito[];
  preguntas?: string[];
}

/** Un examen medido al menos dos veces: el primer y el último valor, tal como están escritos. */
export interface CambioAnalito {
  nombre: string;
  mediciones: number;
  desde: MedicionResumida;
  hasta: MedicionResumida;
}

export interface MedicionResumida {
  fecha: string | null;
  valorTexto: string;
  unidad: string | null;
  marca: string | null;
  cita: number;
}

export type TipoEvento = "CONSULTA" | "EXAMEN" | "HOSPITALIZACION" | "PROCEDIMIENTO" | "FORMULA" | "CONTROL" | "OTRO";

/** Un hecho con fecha escrito en un documento. `fecha` (ISO) es null si la fecha escrita no se entiende sin dudas. */
export interface EventoClinico {
  fecha: string | null;
  fechaTexto: string;
  /** Para «control en 3 meses»: la fecha del documento que lo indica (no la del control). */
  referencia?: string | null;
  tipo: TipoEvento;
  texto: string;
  cita: number;
}

/** Un valor de laboratorio tal como lo imprime el documento. Rango y marca solo si vienen impresos. */
export interface ValorAnalito {
  fecha: string | null;
  fechaTexto: string | null;
  valor: number;
  valorTexto: string;
  unidad: string | null;
  rango: string | null;
  marca: string | null;
  cita: number;
}

export interface Analito {
  clave: string;
  nombre: string;
  unidades: string[];
  /** Falso si el mismo examen aparece con unidades distintas: no se grafica junto. */
  comparable: boolean;
  valores: ValorAnalito[];
}

export interface AdvertenciaCruzada {
  texto: string;
  medicamento: string;
  dato: string;
  /** Citas (desde 1) al documento: la del medicamento y la del dato con el que se compara. */
  citaMedicamento: number;
  citaDato: number;
  /** Número de la ficha citada (desde 1). */
  ficha: number;
}

export interface HallazgoExplicado {
  texto: string;
  /** Número (desde 1) de la cita que respalda el hallazgo. */
  cita: number | null;
}

export interface TerminoExplicado {
  termino: string;
  explicacion: string;
}

/* ---- Medicamentos de Colombia (datos abiertos de INVIMA) ---- */
export interface FuenteDato {
  conjunto: string;
  datasetId: string | null;
  /** Nulo cuando la fuente es un documento que subió la persona (un prospecto). */
  enlace: string | null;
  cargadoAt: string | null;
  licencia: string;
}

export interface CitaRegistro {
  tipo: "REGISTRO_INVIMA";
  id: string;
  cum: string;
  producto: string | null;
  titular: string | null;
  registroSanitario: string | null;
  estadoRegistro: string | null;
  conjunto: "VIGENTE" | "RENOVACION" | "OTROS" | "VENCIDO";
  fechaExpedicion: string | null;
  fechaVencimiento: string | null;
  atc: string | null;
  descripcionAtc: string | null;
  formaFarmaceutica: string | null;
  viaAdministracion: string | null;
  principiosActivos: { nombre: string; cantidad: string | null; unidad: string | null }[];
  presentacion: string | null;
  presentaciones: number;
  fuente: FuenteDato;
}

export interface CitaPrecio {
  tipo: "PRECIO_REGULADO";
  id: string;
  cum: string;
  medicamento: string | null;
  precioInstitucional: string | null;
  precioComercial: string | null;
  precioFinalComercial: string | null;
  circular: string | null;
  vigenciaDesde: string | null;
  fuente: FuenteDato;
}

export interface CitaAgregada {
  tipo: "CONSULTA_AGREGADA";
  id: string;
  filtros: Record<string, string>;
  coincidenciasCum: number;
  registrosSanitarios: number;
  titularesDistintos: number;
  porConjunto: { conjunto: string; cum: number; registros: number }[];
  fuente: FuenteDato;
}

/** Sección de una ficha técnica oficial (CIMA, AEMPS): contraindicaciones, interacciones, reacciones… */
export interface CitaFicha {
  tipo: "FICHA_TECNICA";
  id: string;
  medicamento: string | null;
  principioActivo: string | null;
  registro: string | null;
  seccion: string;
  titulo: string;
  extractoLiteral: string;
  extractoTruncado: boolean;
  /** «PROSPECTO» cuando viene de un prospecto que subió la persona; ausente si es una ficha oficial. */
  origen?: "PROSPECTO";
  nombreArchivo?: string;
  paginaInicio?: number;
  fuente: FuenteDato;
}

/** Fuente oficial a la que se remite (solo enlace: no se copia su contenido). */
export interface FuenteOficial {
  nombre: string;
  url: string;
}

export type CitaMedicamento = CitaRegistro | CitaPrecio | CitaAgregada | CitaFicha;

export interface RespuestaMedicamentos {
  consultaId: string;
  urgencia?: Urgencia | null;
  pregunta?: string;
  respuestaAnalitica: string;
  sinEvidencia: boolean;
  alertas: string[];
  citas: CitaMedicamento[];
  aviso: string;
  fuentesOficiales?: FuenteOficial[];
  limiteClinico?: { codigo: "dosis" | "receta" | "diagnostico" } | null;
  totalCoincidencias?: number;
  modeloLlm: string | null;
  latenciaMs: number;
}

export interface FuenteCargada {
  fuente: string;
  datasetId: string;
  nombre: string;
  filas: number;
  cargadoAt: string;
}

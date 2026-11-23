import type { EstadoIndexacion, TipoDocumento, TipoExpediente } from "../api/tipos";

/** Extensiones que MedTender acepta como documento: PDF y fotos o escaneos. */
export const EXTENSIONES_DOCUMENTO = /\.(pdf|jpe?g|png|heic|heif)$/i;
const EXTENSIONES_IMAGEN = /\.(jpe?g|png|heic|heif)$/i;

export const esImagen = (nombre: string) => EXTENSIONES_IMAGEN.test(nombre);
/** Los navegadores (salvo Safari) no pueden mostrar HEIC. */
export const esHeic = (nombre: string) => /\.(heic|heif)$/i.test(nombre);

/** Pasos visibles del pipeline (el orden importa para la línea de tiempo). */
export const PASOS: { estado: EstadoIndexacion; etiqueta: string; descripcion: string }[] = [
  { estado: "VALIDANDO", etiqueta: "Antivirus", descripcion: "Revisando el PDF (antivirus y estructura)" },
  { estado: "EN_COLA", etiqueta: "En cola", descripcion: "En cola de procesamiento" },
  { estado: "EXTRAYENDO_OCR", etiqueta: "Texto y OCR", descripcion: "Extrayendo el texto (OCR en páginas escaneadas)" },
  { estado: "FRAGMENTANDO", etiqueta: "Fragmentos", descripcion: "Dividiendo el texto en fragmentos" },
  { estado: "VECTORIZANDO", etiqueta: "Vectores", descripcion: "Generando los vectores de búsqueda" },
  { estado: "INDEXADO_Y_PURGADO", etiqueta: "Original borrado", descripcion: "Índice verificado y original eliminado del servidor" },
];

const ORDEN: Record<EstadoIndexacion, number> = {
  RECIBIDO: 0,
  VALIDANDO: 0,
  EN_COLA: 1,
  EXTRAYENDO_OCR: 2,
  FRAGMENTANDO: 3,
  VECTORIZANDO: 4,
  INDEXADO_PENDIENTE_PURGA: 5,
  INDEXADO_Y_PURGADO: 5,
  ERROR_PURGADO: -1,
};

export type EstadoPaso = "hecho" | "actual" | "pendiente";

export function estadoPaso(actual: EstadoIndexacion, indice: number): EstadoPaso {
  const posicion = ORDEN[actual];
  if (actual === "INDEXADO_Y_PURGADO" || indice < posicion) return "hecho";
  return indice === posicion ? "actual" : "pendiente";
}

export const esFinal = (e: EstadoIndexacion) => e === "INDEXADO_Y_PURGADO" || e === "ERROR_PURGADO";
export const esConsultable = (e: EstadoIndexacion) =>
  e === "INDEXADO_Y_PURGADO" || e === "INDEXADO_PENDIENTE_PURGA";

export const TIPOS_DOCUMENTO: Record<TipoDocumento, string> = {
  PLIEGO: "Pliego de condiciones",
  ADENDA: "Adenda",
  FICHA_TECNICA: "Ficha técnica",
  REGISTRO_SANITARIO: "Registro sanitario",
  HISTORIA_CLINICA: "Historia clínica",
  PRESUPUESTO: "Presupuesto",
  PROSPECTO: "Prospecto de medicamento",
};

export const TIPOS_EXPEDIENTE: Record<TipoExpediente, string> = {
  LICITACION_MEDICAMENTOS: "Licitación de medicamentos",
  DOTACION_BIOMEDICA: "Dotación biomédica",
  AUDITORIA_CLINICA: "Auditoría clínica",
};

export function etiquetaDocumento(tipo: TipoDocumento, numeroAdenda?: number | null): string {
  return tipo === "ADENDA" && numeroAdenda ? `Adenda N° ${numeroAdenda}` : TIPOS_DOCUMENTO[tipo];
}

export function tamano(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

export function fecha(iso: string): string {
  return new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

export const paginas = (inicio: number, fin: number) => (inicio === fin ? `pág. ${inicio}` : `págs. ${inicio}–${fin}`);

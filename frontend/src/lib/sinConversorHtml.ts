/**
 * Sustituye a html2canvas, canvg y DOMPurify en el build. jsPDF solo los usa para convertir HTML o SVG a PDF
 * (`doc.html()`), y MedTender dibuja sus PDF con texto. Sin esto se compilaban y la app instalada los guardaba
 * en el teléfono (unos 400 KB).
 */
export default function noIncluido(): never {
  throw new Error("MedTender no convierte HTML a PDF: esta parte de jsPDF no va en el build");
}

import type { Cita, RespuestaConsulta } from "../api/tipos";

const fmtFecha = (iso: string | null | undefined) =>
  iso ? new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" }) : "";

/** Cómo se cita una fuente en el papel: archivo y página. */
export const fuente = (c: Cita | undefined) =>
  c ? `${c.nombreArchivo}, pág. ${c.paginaInicio}${c.paginaFin > c.paginaInicio ? `–${c.paginaFin}` : ""}` : "";

/**
 * Arma el PDF de «Preparar mi cita» en el navegador (jsPDF, cargado solo al pulsar el botón). El archivo no pasa
 * por el servidor. Cada dato lleva su número de cita y al final van las fuentes (archivo y página).
 */
export async function armarPdfCita(r: RespuestaConsulta, preguntas: string[]): Promise<Blob> {
  const { jsPDF } = await import("jspdf");
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const ancho = doc.internal.pageSize.getWidth();
  const alto = doc.internal.pageSize.getHeight();
  const margen = 18;
  const util = ancho - margen * 2;
  let y = margen;

  const salto = (necesario: number) => {
    if (y + necesario > alto - 18) {
      doc.addPage();
      y = margen;
    }
  };
  const parrafo = (texto: string, tam = 10, estilo: "normal" | "bold" = "normal", color: [number, number, number] = [20, 33, 46]) => {
    doc.setFont("helvetica", estilo);
    doc.setFontSize(tam);
    doc.setTextColor(...color);
    const lineas = doc.splitTextToSize(texto, util) as string[];
    const interlinea = tam * 0.45;
    for (const l of lineas) {
      salto(interlinea);
      doc.text(l, margen, y);
      y += interlinea;
    }
    y += 1.5;
  };
  const titulo = (texto: string) => {
    salto(14);
    y += 3;
    parrafo(texto, 12, "bold", [11, 46, 74]);
    doc.setDrawColor(211, 220, 229);
    doc.line(margen, y - 2, margen + util, y - 2);
    y += 1;
  };
  const cita = (n: number) => ` [${n}]`;

  parrafo("Resumen para mi cita", 18, "bold", [11, 46, 74]);
  parrafo(`Preparado con MedTender el ${new Date().toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" })}.`, 9, "normal", [90, 108, 128]);
  if (r.avisoGeneral) parrafo(r.avisoGeneral, 9, "normal", [90, 108, 128]);

  if ((r.eventos ?? []).length) {
    titulo("Lo más reciente en mis documentos");
    for (const e of r.eventos ?? []) {
      const cuando = e.fecha ? fmtFecha(e.fecha) : e.referencia ? `${e.fechaTexto} (documento del ${fmtFecha(e.referencia)})` : e.fechaTexto;
      parrafo(`• ${cuando}: ${e.texto}${cita(e.cita)}`);
    }
  }
  if ((r.cambios ?? []).length) {
    titulo("Exámenes que cambiaron entre dos fechas");
    for (const c of r.cambios ?? []) {
      const v = (m: typeof c.desde) => `${m.valorTexto}${m.unidad ? ` ${m.unidad}` : ""}${m.marca ? ` (marcado ${m.marca})` : ""} el ${fmtFecha(m.fecha)}${cita(m.cita)}`;
      parrafo(`• ${c.nombre}: ${v(c.desde)}; después, ${v(c.hasta)}`);
    }
    parrafo("Valores tal como los imprime cada documento; los rangos pueden cambiar de un laboratorio a otro.", 8, "normal", [90, 108, 128]);
  }
  const listas: [string, { nombre?: string; texto?: string; cita: number }[]][] = [
    ["Medicamentos que aparecen en mis documentos", r.medicamentos ?? []],
    ["Diagnósticos que escriben mis documentos", r.diagnosticos ?? []],
    ["Alergias que registran mis documentos", r.alergias ?? []],
  ];
  for (const [t, items] of listas) {
    if (!items.length) continue;
    titulo(t);
    for (const x of items) parrafo(`• ${x.nombre ?? x.texto}${cita(x.cita)}`);
  }

  titulo("Preguntas para mi médico");
  preguntas.forEach((q, i) => {
    parrafo(`${i + 1}. ${q}`);
    salto(12);
    doc.setDrawColor(211, 220, 229);
    doc.line(margen + 4, y + 3, margen + util, y + 3);
    doc.line(margen + 4, y + 9, margen + util, y + 9);
    y += 13;
  });

  const usadas = new Set<number>([
    ...(r.eventos ?? []).map((e) => e.cita),
    ...(r.cambios ?? []).flatMap((c) => [c.desde.cita, c.hasta.cita]),
    ...listas.flatMap(([, items]) => items.map((x) => x.cita)),
  ]);
  if (usadas.size) {
    titulo("Fuentes");
    [...usadas].sort((a, b) => a - b).forEach((n) => parrafo(`[${n}] ${fuente(r.citas[n - 1])}`, 8, "normal", [90, 108, 128]));
  }

  const paginas = doc.getNumberOfPages();
  for (let p = 1; p <= paginas; p++) {
    doc.setPage(p);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(90, 108, 128);
    doc.text("MedTender · No es un diagnóstico ni reemplaza a tu médico. En una urgencia, llama al 123.", margen, alto - 10);
    doc.text(`${p} / ${paginas}`, ancho - margen, alto - 10, { align: "right" });
  }
  return doc.output("blob");
}

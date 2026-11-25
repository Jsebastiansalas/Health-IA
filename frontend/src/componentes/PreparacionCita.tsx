import { useState } from "react";
import { toast } from "sonner";
import type { RespuestaConsulta } from "../api/tipos";
import { CalendarBlank, ChartLine, DownloadSimple, Pill, PlusCircle, SearchX, ShareNetwork, Stethoscope, TriangleAlert, X } from "../iconos";
import { armarPdfCita } from "../lib/pdfCita";
import { Boton } from "./ui/Boton";
import { Insignia } from "./ui/Insignia";

const fmtFecha = (iso: string | null | undefined) =>
  iso ? new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" }) : "";

function Chip({ n, alIr }: { n: number; alIr: (n: number) => void }) {
  return (
    <button
      type="button"
      onClick={() => alIr(n)}
      className="mx-0.5 inline-grid size-5 -translate-y-0.5 place-items-center rounded-lg bg-cita align-middle text-xs font-semibold text-cita-tx transition-colors hover:bg-primario hover:text-primario-tx"
      aria-label={`Ir a la cita ${n}`}
    >
      {n}
    </button>
  );
}

const nombreArchivo = () => `resumen-para-mi-cita-${new Date().toISOString().slice(0, 10)}.pdf`;

/**
 * «Preparar mi cita»: lo que dicen tus documentos en una página, con su cita, y preguntas para tu médico que
 * puedes editar antes de descargar el PDF. El PDF se arma en tu navegador: no pasa por el servidor.
 */
export function PreparacionCita({ respuesta: r, alIrACita }: { respuesta: RespuestaConsulta; alIrACita: (n: number) => void }) {
  const [preguntas, setPreguntas] = useState<string[]>(() => r.preguntas ?? []);
  const [nueva, setNueva] = useState("");
  const [armando, setArmando] = useState(false);
  const puedeCompartir = typeof navigator !== "undefined" && typeof navigator.canShare === "function";

  if (r.sinEvidencia) {
    return (
      <div>
        <Insignia tono="aviso" className="mb-4">
          <SearchX className="size-4" aria-hidden />
          Aún no hay qué resumir
        </Insignia>
        <p className="text-sm leading-relaxed">{r.respuestaAnalitica}</p>
      </div>
    );
  }

  const limpias = () => preguntas.map((q) => q.trim()).filter(Boolean);

  async function descargar() {
    setArmando(true);
    try {
      const blob = await armarPdfCita(r, limpias());
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = nombreArchivo();
      a.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } catch {
      toast.error("No se pudo armar el PDF");
    } finally {
      setArmando(false);
    }
  }

  async function compartir() {
    setArmando(true);
    try {
      const archivo = new File([await armarPdfCita(r, limpias())], nombreArchivo(), { type: "application/pdf" });
      if (!navigator.canShare?.({ files: [archivo] })) {
        toast.error("Este dispositivo no permite compartir archivos; descárgalo y envíalo.");
        return;
      }
      await navigator.share({ files: [archivo], title: "Resumen para mi cita" });
    } catch (e) {
      if ((e as DOMException)?.name !== "AbortError") toast.error("No se pudo compartir el PDF");
    } finally {
      setArmando(false);
    }
  }

  const listas: [string, typeof Pill, { nombre?: string; texto?: string; cita: number }[]][] = [
    ["Medicamentos que aparecen en tus documentos", Pill, r.medicamentos ?? []],
    ["Diagnósticos que escriben tus documentos", Stethoscope, r.diagnosticos ?? []],
    ["Alergias que registran tus documentos", TriangleAlert, r.alergias ?? []],
  ];

  return (
    <div className="space-y-6 text-sm leading-relaxed">
      {r.avisoGeneral && <p className="rounded-lg bg-panel-2 px-4 py-3 text-texto-2">{r.avisoGeneral}</p>}

      {(r.eventos ?? []).length > 0 && (
        <section aria-labelledby={`rec-${r.consultaId}`}>
          <h3 id={`rec-${r.consultaId}`} className="mb-2 flex items-center gap-2 font-semibold text-primario-osc">
            <CalendarBlank className="size-4" aria-hidden />
            Lo más reciente en tus documentos
          </h3>
          <ul className="space-y-1">
            {(r.eventos ?? []).map((e, i) => (
              <li key={`${e.cita}-${i}`} className="ml-4 list-disc">
                <span className="num font-medium">
                  {e.fecha ? fmtFecha(e.fecha) : e.referencia ? `${e.fechaTexto} (documento del ${fmtFecha(e.referencia)})` : e.fechaTexto}
                </span>
                : {e.texto}
                <Chip n={e.cita} alIr={alIrACita} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {(r.cambios ?? []).length > 0 && (
        <section aria-labelledby={`camb-${r.consultaId}`}>
          <h3 id={`camb-${r.consultaId}`} className="mb-2 flex items-center gap-2 font-semibold text-primario-osc">
            <ChartLine className="size-4" aria-hidden />
            Exámenes que cambiaron entre dos fechas
          </h3>
          <ul className="space-y-1">
            {(r.cambios ?? []).map((c) => (
              <li key={c.nombre} className="ml-4 list-disc">
                <span className="font-medium">{c.nombre}</span>: <span className="num">{c.desde.valorTexto} {c.desde.unidad}</span> el {fmtFecha(c.desde.fecha)}
                <Chip n={c.desde.cita} alIr={alIrACita} />; después, <span className="num">{c.hasta.valorTexto} {c.hasta.unidad}</span> el{" "}
                {fmtFecha(c.hasta.fecha)}
                <Chip n={c.hasta.cita} alIr={alIrACita} />
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-texto-3">Valores tal como los imprime cada documento. No se interpretan.</p>
        </section>
      )}

      {listas.map(([titulo, Icono, items]) =>
        items.length === 0 ? null : (
          <section key={titulo}>
            <h3 className="mb-2 flex items-center gap-2 font-semibold text-primario-osc">
              <Icono className="size-4" aria-hidden />
              {titulo}
            </h3>
            <ul className="space-y-1">
              {items.map((x, i) => (
                <li key={`${x.cita}-${i}`} className="ml-4 list-disc">
                  {x.nombre ?? x.texto}
                  <Chip n={x.cita} alIr={alIrACita} />
                </li>
              ))}
            </ul>
          </section>
        ),
      )}

      <section aria-labelledby={`preg-${r.consultaId}`} className="rounded-xl border border-borde p-4">
        <h3 id={`preg-${r.consultaId}`} className="font-semibold text-texto">
          Preguntas para tu médico
        </h3>
        <p className="mt-1 text-xs text-texto-3">Son sugerencias: cámbialas, bórralas o agrega las tuyas. Van al PDF tal como las dejes.</p>
        <ol className="mt-3 space-y-2">
          {preguntas.map((q, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="num mt-2 w-5 shrink-0 text-right text-texto-3">{i + 1}.</span>
              <textarea
                value={q}
                onChange={(e) => setPreguntas((ps) => ps.map((x, k) => (k === i ? e.target.value : x)))}
                rows={2}
                aria-label={`Pregunta ${i + 1}`}
                className="min-h-10 flex-1 resize-y rounded-lg border border-borde bg-panel px-3 py-2 outline-none focus:border-texto"
              />
              <button
                type="button"
                onClick={() => setPreguntas((ps) => ps.filter((_, k) => k !== i))}
                className="mt-1.5 grid size-8 place-items-center rounded-lg text-texto-3 transition-colors hover:bg-panel-2 hover:text-texto"
                aria-label={`Quitar la pregunta ${i + 1}`}
              >
                <X className="size-4" aria-hidden />
              </button>
            </li>
          ))}
        </ol>
        <form
          className="mt-3 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (!nueva.trim()) return;
            setPreguntas((ps) => [...ps, nueva.trim()]);
            setNueva("");
          }}
        >
          <input
            value={nueva}
            onChange={(e) => setNueva(e.target.value)}
            placeholder="Escribe otra pregunta"
            aria-label="Nueva pregunta"
            className="h-10 min-w-0 flex-1 rounded-lg border border-borde bg-panel px-3 outline-none focus:border-texto"
          />
          <Boton type="submit" variante="secundario" disabled={!nueva.trim()}>
            <PlusCircle className="size-4" aria-hidden />
            Agregar
          </Boton>
        </form>
      </section>

      {r.alertas.length > 0 && (
        <ul className="space-y-1 text-texto-2">
          {r.alertas.map((t) => (
            <li key={t} className="flex items-start gap-2">
              <TriangleAlert className="mt-0.5 size-4 shrink-0 text-aviso" aria-hidden />
              {t}
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap gap-2">
        <Boton variante="primario" onClick={() => void descargar()} cargando={armando}>
          {!armando && <DownloadSimple className="size-4" aria-hidden />}
          Descargar PDF
        </Boton>
        {puedeCompartir && (
          <Boton variante="secundario" onClick={() => void compartir()} disabled={armando}>
            <ShareNetwork className="size-4" aria-hidden />
            Compartir
          </Boton>
        )}
      </div>
      <p className="text-xs text-texto-3">El PDF se arma en tu dispositivo: no se guarda en el servidor.</p>
    </div>
  );
}

import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Cita } from "../api/tipos";
import {
  carpetaRecordada,
  elegirCarpeta,
  localizarOriginal,
  soportaCarpetas,
  tienePermiso,
  type PdfLocal,
} from "../lib/carpetaLocal";
import { etiquetaDocumento, paginas } from "../lib/formato";
import { mismoHash, sha256Hex } from "../lib/sha256";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

type Estado =
  | { fase: "preparando" }
  | { fase: "sin-carpeta" }
  | { fase: "permiso"; carpeta: FileSystemDirectoryHandle }
  | { fase: "buscando"; revisados: number }
  | { fase: "no-encontrado" }
  | { fase: "distinto"; pdf: PdfLocal; hashLocal: string }
  | { fase: "listo"; pdf: PdfLocal; verificado: boolean; porNombre: boolean }
  | { fase: "error"; mensaje: string };

/**
 * Abre el PDF ORIGINAL desde el PC del usuario, verifica su SHA-256 contra el guardado en el
 * servidor y lo muestra en la página citada. Todo ocurre en memoria del navegador: el archivo
 * no se sube a ningún lado.
 */
export function VisorLocal({ cita, alCerrar }: { cita: Cita; alCerrar: () => void }) {
  const [estado, setEstado] = useState<Estado>({ fase: "preparando" });

  const buscar = useCallback(
    async (carpeta: FileSystemDirectoryHandle) => {
      setEstado({ fase: "buscando", revisados: 0 });
      try {
        const r = await localizarOriginal(carpeta, cita.nombreArchivo, cita.sha256Original, (n) =>
          setEstado({ fase: "buscando", revisados: n }),
        );
        if (r.tipo === "coincide") setEstado({ fase: "listo", pdf: r.pdf, verificado: true, porNombre: r.porNombre });
        else if (r.tipo === "distinto") setEstado({ fase: "distinto", pdf: r.pdf, hashLocal: r.hashLocal });
        else setEstado({ fase: "no-encontrado" });
      } catch (e) {
        setEstado({ fase: "error", mensaje: e instanceof Error ? e.message : String(e) });
      }
    },
    [cita.nombreArchivo, cita.sha256Original],
  );

  // Al abrir: si ya hay una carpeta recordada con permiso, se busca directamente.
  useEffect(() => {
    let vigente = true;
    (async () => {
      if (!soportaCarpetas()) return vigente && setEstado({ fase: "sin-carpeta" });
      const carpeta = await carpetaRecordada();
      if (!vigente) return;
      if (!carpeta) return setEstado({ fase: "sin-carpeta" });
      if (await tienePermiso(carpeta)) buscar(carpeta);
      else setEstado({ fase: "permiso", carpeta });
    })();
    return () => {
      vigente = false;
    };
  }, [buscar]);

  useEffect(() => {
    const teclado = (e: KeyboardEvent) => e.key === "Escape" && alCerrar();
    window.addEventListener("keydown", teclado);
    return () => window.removeEventListener("keydown", teclado);
  }, [alCerrar]);

  async function vincular() {
    try {
      buscar(await elegirCarpeta());
    } catch (e) {
      if ((e as DOMException).name !== "AbortError") setEstado({ fase: "error", mensaje: String(e) });
    }
  }

  async function reactivar(carpeta: FileSystemDirectoryHandle) {
    if (await tienePermiso(carpeta, true)) buscar(carpeta);
  }

  async function elegirArchivo(archivo: File | undefined) {
    if (!archivo) return;
    setEstado({ fase: "buscando", revisados: 1 });
    const hash = await sha256Hex(await archivo.arrayBuffer());
    const pdf = { archivo, ruta: archivo.name };
    setEstado(
      mismoHash(hash, cita.sha256Original)
        ? { fase: "listo", pdf, verificado: true, porNombre: archivo.name === cita.nombreArchivo }
        : { fase: "distinto", pdf, hashLocal: hash },
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true" aria-label="Visor del PDF original">
      <button aria-label="Cerrar visor" className="flex-1 bg-tinta/45 backdrop-blur-[2px]" onClick={alCerrar} />
      <aside className="flex h-full w-full max-w-4xl animate-aparecer flex-col border-l border-papel-3 bg-papel shadow-2xl">
        <header className="relative flex items-start justify-between gap-4 border-b border-papel-3 px-6 py-4">
          <div className="min-w-0">
            <p className="etiqueta">
              Original en su PC · {etiquetaDocumento(cita.tipoDocumento, cita.numeroAdenda)} ·{" "}
              {paginas(cita.paginaInicio, cita.paginaFin)}
            </p>
            <h2 className="truncate font-display text-2xl">{cita.nombreArchivo}</h2>
            <p className="mt-1 truncate font-mono text-[0.66rem] text-grafito" title={cita.sha256Original}>
              SHA-256 registrado {cita.sha256Original}
            </p>
          </div>
          {estado.fase === "listo" && (
            <span className="sello absolute top-16 right-6 animate-estampar bg-papel text-sm text-clinico">
              ✓ SHA-256 coincide
            </span>
          )}
          {estado.fase === "distinto" && (
            <span className="sello absolute top-16 right-6 animate-estampar bg-papel text-sm text-sello">
              ✕ No coincide
            </span>
          )}
          <button className="boton boton-linea" onClick={alCerrar}>Cerrar</button>
        </header>

        <div className="flex-1 overflow-auto">
          {estado.fase === "listo" ? (
            <LectorPdf pdf={estado.pdf} cita={cita} />
          ) : (
            <div className="mx-auto max-w-lg px-6 py-16">
              <Indicaciones estado={estado} cita={cita} alVincular={vincular} alReactivar={reactivar}
                alElegirArchivo={elegirArchivo} />
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

function Indicaciones({
  estado,
  cita,
  alVincular,
  alReactivar,
  alElegirArchivo,
}: {
  estado: Exclude<Estado, { fase: "listo" }>;
  cita: Cita;
  alVincular: () => void;
  alReactivar: (c: FileSystemDirectoryHandle) => void;
  alElegirArchivo: (f: File | undefined) => void;
}) {
  const elegirManual = (
    <label className="boton boton-linea cursor-pointer">
      Elegir el PDF manualmente
      <input type="file" accept="application/pdf,.pdf" className="sr-only"
        onChange={(e) => alElegirArchivo(e.target.files?.[0])} />
    </label>
  );
  const privacidad = (
    <p className="mt-8 border-t border-papel-3 pt-4 text-xs text-grafito">
      El archivo se lee en la memoria de este navegador y se compara por su huella SHA-256. No se sube al servidor.
    </p>
  );

  switch (estado.fase) {
    case "preparando":
    case "buscando":
      return (
        <p className="etiqueta animate-pulse">
          {estado.fase === "buscando" && estado.revisados > 0
            ? `Comparando huellas SHA-256… ${estado.revisados} PDF revisados`
            : `Buscando «${cita.nombreArchivo}» en su carpeta…`}
        </p>
      );
    case "sin-carpeta":
      return (
        <>
          <h3 className="font-display text-3xl">Vincule su carpeta local de PDFs</h3>
          <p className="mt-3 text-tinta-2">
            Para ver la página citada, MedTender necesita leer el original desde su computador. Elija la carpeta donde
            guarda los PDF del expediente; el navegador la recordará.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            {soportaCarpetas() ? (
              <button className="boton boton-tinta" onClick={alVincular}>Vincular carpeta local de PDFs</button>
            ) : (
              <p className="text-sm text-ambar">
                Su navegador no permite vincular carpetas (use Chrome o Edge). Puede elegir el archivo a mano.
              </p>
            )}
            {elegirManual}
          </div>
          {privacidad}
        </>
      );
    case "permiso":
      return (
        <>
          <h3 className="font-display text-3xl">Reactive el acceso a «{estado.carpeta.name}»</h3>
          <p className="mt-3 text-tinta-2">Por seguridad, el navegador pide confirmar el acceso en cada visita.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <button className="boton boton-tinta" onClick={() => alReactivar(estado.carpeta)}>Permitir lectura</button>
            <button className="boton boton-linea" onClick={alVincular}>Usar otra carpeta</button>
          </div>
          {privacidad}
        </>
      );
    case "no-encontrado":
      return (
        <>
          <h3 className="font-display text-3xl">No encontré el original</h3>
          <p className="mt-3 text-tinta-2">
            Ningún PDF de la carpeta coincide por nombre ni por huella SHA-256 con «{cita.nombreArchivo}». Quizá está en
            otra carpeta o en otro equipo.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <button className="boton boton-tinta" onClick={alVincular}>Elegir otra carpeta</button>
            {elegirManual}
          </div>
          {privacidad}
        </>
      );
    case "distinto":
      return (
        <>
          <h3 className="font-display text-3xl text-sello">El archivo no es el mismo que se indexó</h3>
          <p className="mt-3 text-tinta-2">
            «{estado.pdf.ruta}» tiene el nombre esperado pero su contenido cambió. Las citas corresponden a la versión
            indexada: revisarlas en otra versión podría llevar a conclusiones equivocadas.
          </p>
          <dl className="mt-5 space-y-1 font-mono text-[0.68rem]">
            <div><dt className="inline text-grafito">Indexado: </dt><dd className="inline">{cita.sha256Original}</dd></div>
            <div><dt className="inline text-grafito">En su PC: </dt><dd className="inline text-sello">{estado.hashLocal}</dd></div>
          </dl>
          <div className="mt-6 flex flex-wrap gap-3">
            <button className="boton boton-tinta" onClick={alVincular}>Buscar en otra carpeta</button>
            {elegirManual}
          </div>
        </>
      );
    case "error":
      return <p role="alert" className="text-sello">{estado.mensaje}</p>;
  }
}

const normalizar = (t: string) => t.normalize("NFKC").toLowerCase().replace(/\s+/g, " ").trim();

function LectorPdf({ pdf, cita }: { pdf: PdfLocal; cita: Cita }) {
  const lienzo = useRef<HTMLCanvasElement>(null);
  const contenedor = useRef<HTMLDivElement>(null);
  const [documento, setDocumento] = useState<pdfjs.PDFDocumentProxy | null>(null);
  const [pagina, setPagina] = useState(cita.paginaInicio);
  const [extractoEnPagina, setExtractoEnPagina] = useState<boolean | null>(null);

  // Carga en memoria y, si la cita abarca varias páginas, salta a la que contiene el extracto.
  useEffect(() => {
    let tarea: pdfjs.PDFDocumentLoadingTask | null = null;
    let vigente = true;
    (async () => {
      tarea = pdfjs.getDocument({ data: new Uint8Array(await pdf.archivo.arrayBuffer()) });
      const doc = await tarea.promise;
      if (!vigente) return;
      const buscado = normalizar(cita.extractoLiteral).slice(0, 60);
      for (let p = cita.paginaInicio; p <= Math.min(cita.paginaFin, doc.numPages); p++) {
        const contenido = await (await doc.getPage(p)).getTextContent();
        const texto = normalizar(contenido.items.map((i) => ("str" in i ? i.str : "")).join(" "));
        if (texto.includes(buscado)) {
          setPagina(p);
          setExtractoEnPagina(true);
          break;
        }
      }
      setExtractoEnPagina((v) => v ?? false);
      setDocumento(doc);
    })();
    return () => {
      vigente = false;
      tarea?.destroy();
    };
  }, [pdf, cita]);

  useEffect(() => {
    if (!documento || !lienzo.current || !contenedor.current) return;
    let render: pdfjs.RenderTask | null = null;
    (async () => {
      const p = await documento.getPage(Math.min(Math.max(1, pagina), documento.numPages));
      const ancho = contenedor.current!.clientWidth - 48;
      const base = p.getViewport({ scale: 1 });
      const escala = ancho / base.width;
      const viewport = p.getViewport({ scale: escala * window.devicePixelRatio });
      const canvas = lienzo.current!;
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.width = `${viewport.width / window.devicePixelRatio}px`;
      render = p.render({ canvas, viewport });
      await render.promise.catch(() => undefined);
    })();
    return () => render?.cancel();
  }, [documento, pagina]);

  const total = documento?.numPages ?? 0;
  return (
    <div ref={contenedor} className="px-6 py-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-tinta-2">
          {pdf.ruta}
          {extractoEnPagina === true && <span className="ml-2 text-clinico">· el extracto citado está en esta página</span>}
          {extractoEnPagina === false && (
            <span className="ml-2 text-ambar">· el extracto no se ubicó automáticamente (texto escaneado o tabla)</span>
          )}
        </p>
        <div className="flex items-center gap-2">
          <button className="boton boton-linea !px-3 !py-1" disabled={pagina <= 1} onClick={() => setPagina((p) => p - 1)}>←</button>
          <span className="font-mono text-sm">{pagina} / {total || "…"}</span>
          <button className="boton boton-linea !px-3 !py-1" disabled={pagina >= total} onClick={() => setPagina((p) => p + 1)}>→</button>
        </div>
      </div>
      <blockquote className="mb-4 border-l-4 border-sello bg-sello-claro/60 px-4 py-2 font-display text-sm italic">
        «{cita.extractoLiteral}»
      </blockquote>
      <canvas ref={lienzo} className="mx-auto block bg-white shadow-lg" />
    </div>
  );
}

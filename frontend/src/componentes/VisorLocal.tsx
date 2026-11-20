import * as Dialog from "@radix-ui/react-dialog";
import {
  BadgeCheck,
  ChevronLeft,
  ChevronRight,
  FolderOpen,
  FolderSearch,
  LockKeyhole,
  Maximize2,
  OctagonAlert,
  SearchX,
  ShieldAlert,
  ShieldCheck,
  X,
  ZoomIn,
  ZoomOut,
  type LucideIcon,
} from "lucide-react";
import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type { Cita } from "../api/tipos";
import {
  carpetaRecordada,
  elegirCarpeta,
  localizarOriginal,
  soportaCarpetas,
  tienePermiso,
  type PdfLocal,
} from "../lib/carpetaLocal";
import { cn } from "../lib/cn";
import { etiquetaDocumento, paginas } from "../lib/formato";
import { mismoHash, sha256Hex } from "../lib/sha256";
import { Boton } from "./ui/Boton";
import { Esqueleto } from "./ui/Esqueleto";
import { Insignia } from "./ui/Insignia";

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
    <Dialog.Root open onOpenChange={(abierto) => !abierto && alCerrar()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 " />
        <Dialog.Content
          aria-describedby={undefined}
          className="vidrio-solido fixed inset-y-0 right-0 z-50 flex w-full max-w-5xl flex-col outline-none data-[state=open]:animate-[aparecer_350ms_var(--ease-salida)] sm:inset-y-3 sm:right-3 sm:rounded-3xl"
        >
          <header className="flex items-start justify-between gap-4 border-b border-ink/8 px-5 py-4 sm:px-6">
            <div className="min-w-0">
              <p className="flex items-center gap-1.5 text-[0.78rem] font-medium text-hema">
                <FolderOpen className="size-3.5" aria-hidden />
                Original en tu equipo · {etiquetaDocumento(cita.tipoDocumento, cita.numeroAdenda)} ·{" "}
                {paginas(cita.paginaInicio, cita.paginaFin)}
              </p>
              <Dialog.Title className="mt-0.5 truncate font-display text-2xl font-semibold">
                {cita.nombreArchivo}
              </Dialog.Title>
              <p className="mt-1 truncate font-mono text-[0.7rem] text-tx-3" title={cita.sha256Original}>
                SHA-256 registrado {cita.sha256Original}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {estado.fase === "listo" && (
                <Insignia tono="hema" className="hidden animate-sello sm:inline-flex">
                  <BadgeCheck className="size-3.5" aria-hidden />
                  SHA-256 coincide
                </Insignia>
              )}
              {estado.fase === "distinto" && (
                <Insignia tono="coral" className="hidden animate-sello sm:inline-flex">
                  <ShieldAlert className="size-3.5" aria-hidden />
                  No coincide
                </Insignia>
              )}
              <Dialog.Close asChild>
                <Boton variante="secundario" tamano="icono" aria-label="Cerrar visor">
                  <X className="size-5" aria-hidden />
                </Boton>
              </Dialog.Close>
            </div>
          </header>

          <div className="min-h-0 flex-1">
            {estado.fase === "listo" ? (
              <LectorPdf pdf={estado.pdf} cita={cita} />
            ) : (
              <div className="grid h-full place-items-center overflow-auto px-6 py-10">
                <Indicaciones
                  estado={estado}
                  cita={cita}
                  alVincular={vincular}
                  alReactivar={reactivar}
                  alElegirArchivo={elegirArchivo}
                />
              </div>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function Fase({
  icono: Icono,
  tono = "hema",
  titulo,
  children,
}: {
  icono: LucideIcon;
  tono?: "hema" | "coral" | "ambar";
  titulo: string;
  children?: ReactNode;
}) {
  const colores = {
    hema: "border-hema/30 bg-hema/10 text-hema",
    coral: "border-coral/35 bg-coral/10 text-coral",
    ambar: "border-ambar/35 bg-ambar/10 text-ambar",
  }[tono];
  return (
    <div className="mx-auto max-w-lg text-center">
      <div className={cn("mx-auto grid size-24 place-items-center rounded-[2rem] border", colores)}>
        <Icono className="size-11" strokeWidth={1.4} aria-hidden />
      </div>
      <h3 className="mt-7 text-3xl font-semibold leading-tight">{titulo}</h3>
      {children}
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
    <label className="relative inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-xl border border-ink/12 bg-ink/[0.06] px-4 text-sm font-semibold text-tx transition-colors hover:border-ink/25 hover:bg-ink/[0.11] focus-within:outline focus-within:outline-2 focus-within:outline-hema">
      Elegir el PDF manualmente
      <input
        type="file"
        accept="application/pdf,.pdf"
        className="sr-only"
        onChange={(e) => alElegirArchivo(e.target.files?.[0])}
      />
    </label>
  );
  const privacidad = (
    <p className="mx-auto mt-9 flex max-w-sm items-start gap-2.5 text-left text-xs leading-relaxed text-tx-3">
      <ShieldCheck className="mt-0.5 size-4 shrink-0 text-hema" aria-hidden />
      El archivo se lee en la memoria de este navegador y se compara por su huella SHA-256. No se sube al servidor.
    </p>
  );
  const acciones = "mt-7 flex flex-wrap justify-center gap-3";

  switch (estado.fase) {
    case "preparando":
    case "buscando":
      return (
        <div className="w-full max-w-md" aria-busy>
          <Fase icono={FolderSearch} titulo="Buscando el original…">
            <p className="mt-3 text-tx-2">
              {estado.fase === "buscando" && estado.revisados > 0
                ? `Comparando huellas SHA-256… ${estado.revisados} PDF revisados`
                : `Buscando «${cita.nombreArchivo}» en tu carpeta…`}
            </p>
          </Fase>
          <Esqueleto className="mx-auto mt-8 h-2 w-64 rounded-full" />
        </div>
      );
    case "sin-carpeta":
      return (
        <div>
          <Fase icono={FolderOpen} titulo="Vincula tu carpeta local de PDFs">
            <p className="mt-3 text-tx-2">
              Para ver la página citada, MedTender necesita leer el original desde tu computador. Elige la carpeta donde
              guardas los PDF del expediente; el navegador la recordará.
            </p>
            <div className={acciones}>
              {soportaCarpetas() ? (
                <Boton variante="primario" tamano="lg" onClick={alVincular}>
                  Vincular carpeta local de PDFs
                </Boton>
              ) : (
                <p className="rounded-xl border border-ambar/30 bg-ambar/10 px-4 py-3 text-sm text-ambar">
                  Tu navegador no permite vincular carpetas (usa Chrome o Edge). Puedes elegir el archivo a mano.
                </p>
              )}
              {elegirManual}
            </div>
          </Fase>
          {privacidad}
        </div>
      );
    case "permiso":
      return (
        <div>
          <Fase icono={LockKeyhole} tono="ambar" titulo={`Reactiva el acceso a «${estado.carpeta.name}»`}>
            <p className="mt-3 text-tx-2">Por seguridad, el navegador pide confirmar el acceso en cada visita.</p>
            <div className={acciones}>
              <Boton variante="primario" tamano="lg" onClick={() => alReactivar(estado.carpeta)}>
                Permitir lectura
              </Boton>
              <Boton tamano="lg" onClick={alVincular}>
                Usar otra carpeta
              </Boton>
            </div>
          </Fase>
          {privacidad}
        </div>
      );
    case "no-encontrado":
      return (
        <div>
          <Fase icono={SearchX} tono="ambar" titulo="No encontré el original">
            <p className="mt-3 text-tx-2">
              Ningún PDF de la carpeta coincide por nombre ni por huella SHA-256 con «{cita.nombreArchivo}». Quizá está
              en otra carpeta o en otro equipo.
            </p>
            <div className={acciones}>
              <Boton variante="primario" tamano="lg" onClick={alVincular}>
                Elegir otra carpeta
              </Boton>
              {elegirManual}
            </div>
          </Fase>
          {privacidad}
        </div>
      );
    case "distinto":
      return (
        <div>
          <Fase icono={ShieldAlert} tono="coral" titulo="El archivo no es el mismo que se indexó">
            <p className="mt-3 text-tx-2">
              «{estado.pdf.ruta}» tiene el nombre esperado pero su contenido cambió. Las citas corresponden a la versión
              indexada: revisarlas en otra versión podría llevar a conclusiones equivocadas.
            </p>
            <dl className="mt-5 space-y-2 rounded-xl border border-ink/10 bg-sala p-4 text-left font-mono text-[0.7rem]">
              <div>
                <dt className="text-tx-3">Indexado</dt>
                <dd className="break-all text-hema">{cita.sha256Original}</dd>
              </div>
              <div>
                <dt className="text-tx-3">En tu equipo</dt>
                <dd className="break-all text-coral">{estado.hashLocal}</dd>
              </div>
            </dl>
            <div className={acciones}>
              <Boton variante="primario" tamano="lg" onClick={alVincular}>
                Buscar en otra carpeta
              </Boton>
              {elegirManual}
            </div>
          </Fase>
        </div>
      );
    case "error":
      return (
        <Fase icono={OctagonAlert} tono="coral" titulo="No se pudo abrir el original">
          <p role="alert" className="mt-3 text-tx-2">
            {estado.mensaje}
          </p>
        </Fase>
      );
  }
}

const normalizar = (t: string) => t.normalize("NFKC").toLowerCase().replace(/\s+/g, " ").trim();
const ZOOMS = [0.6, 0.8, 1, 1.25, 1.6, 2];

function LectorPdf({ pdf, cita }: { pdf: PdfLocal; cita: Cita }) {
  const lienzo = useRef<HTMLCanvasElement>(null);
  const contenedor = useRef<HTMLDivElement>(null);
  const [documento, setDocumento] = useState<pdfjs.PDFDocumentProxy | null>(null);
  const [pagina, setPagina] = useState(cita.paginaInicio);
  const [zoom, setZoom] = useState(2); // índice en ZOOMS: 1,0 = ajustar al ancho
  const [ancho, setAncho] = useState(0);
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

  // El lienzo se recalcula cuando cambia el ancho disponible (ventana o barra lateral).
  useEffect(() => {
    const el = contenedor.current;
    if (!el) return;
    const observador = new ResizeObserver(() => setAncho(el.clientWidth));
    observador.observe(el);
    setAncho(el.clientWidth);
    return () => observador.disconnect();
  }, []);

  useEffect(() => {
    if (!documento || !lienzo.current || !ancho) return;
    let render: pdfjs.RenderTask | null = null;
    (async () => {
      const p = await documento.getPage(Math.min(Math.max(1, pagina), documento.numPages));
      const disponible = Math.max(240, ancho - 48);
      const base = p.getViewport({ scale: 1 });
      const escala = (disponible / base.width) * ZOOMS[zoom]!;
      const viewport = p.getViewport({ scale: escala * window.devicePixelRatio });
      const canvas = lienzo.current!;
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.width = `${viewport.width / window.devicePixelRatio}px`;
      render = p.render({ canvas, viewport });
      await render.promise.catch(() => undefined);
    })();
    return () => render?.cancel();
  }, [documento, pagina, zoom, ancho]);

  const total = documento?.numPages ?? 0;
  const irA = (n: number) => setPagina(Math.min(Math.max(1, n), total || 1));

  // Teclado: ← → cambian de página; + − acercan y alejan.
  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => {
      if (/INPUT|TEXTAREA/.test((e.target as HTMLElement).tagName)) return;
      if (e.key === "ArrowLeft") setPagina((p) => Math.max(1, p - 1));
      else if (e.key === "ArrowRight") setPagina((p) => Math.min(total || 1, p + 1));
      else if (e.key === "+" || e.key === "=") setZoom((z) => Math.min(ZOOMS.length - 1, z + 1));
      else if (e.key === "-") setZoom((z) => Math.max(0, z - 1));
    };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [total]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink/8 px-5 py-3 sm:px-6">
        <p className="min-w-0 text-sm text-tx-2">
          <span className="truncate">{pdf.ruta}</span>
          {extractoEnPagina === true && <span className="ml-2 text-hema">· el extracto citado está en esta página</span>}
          {extractoEnPagina === false && (
            <span className="ml-2 text-ambar">· el extracto no se ubicó automáticamente (texto escaneado o tabla)</span>
          )}
        </p>
        <div className="flex items-center gap-1.5">
          <Boton tamano="icono" variante="fantasma" className="size-9" onClick={() => setZoom((z) => Math.max(0, z - 1))} disabled={zoom === 0} aria-label="Alejar">
            <ZoomOut className="size-[1.1rem]" aria-hidden />
          </Boton>
          <span className="num w-12 text-center text-sm text-tx-2">{Math.round(ZOOMS[zoom]! * 100)} %</span>
          <Boton tamano="icono" variante="fantasma" className="size-9" onClick={() => setZoom((z) => Math.min(ZOOMS.length - 1, z + 1))} disabled={zoom === ZOOMS.length - 1} aria-label="Acercar">
            <ZoomIn className="size-[1.1rem]" aria-hidden />
          </Boton>
          <Boton tamano="icono" variante="fantasma" className="size-9" onClick={() => setZoom(2)} aria-label="Ajustar al ancho">
            <Maximize2 className="size-4" aria-hidden />
          </Boton>
          <span className="mx-2 h-5 w-px bg-ink/10" aria-hidden />
          <Boton tamano="icono" variante="secundario" className="size-9" disabled={pagina <= 1} onClick={() => irA(pagina - 1)} aria-label="Página anterior">
            <ChevronLeft className="size-[1.1rem]" aria-hidden />
          </Boton>
          <span className="num min-w-16 text-center text-sm">
            {pagina} / {total || "…"}
          </span>
          <Boton tamano="icono" variante="secundario" className="size-9" disabled={pagina >= total} onClick={() => irA(pagina + 1)} aria-label="Página siguiente">
            <ChevronRight className="size-[1.1rem]" aria-hidden />
          </Boton>
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        {documento && total > 1 && <Miniaturas documento={documento} actual={pagina} alElegir={irA} />}
        <div ref={contenedor} className="min-w-0 flex-1 overflow-auto px-6 py-5">
          <blockquote className="mx-auto mb-4 max-w-3xl rounded-xl border border-hema/25 bg-hema/[0.07] px-4 py-3 font-display text-[0.95rem] leading-snug">
            <span className="mb-1 block text-[0.72rem] font-medium text-hema">Extracto citado</span>«{cita.extractoLiteral}»
          </blockquote>
          {!documento ? (
            <div className="mx-auto max-w-3xl" aria-busy aria-label="Abriendo el PDF">
              <Esqueleto className="aspect-[1/1.3] w-full rounded-lg" />
            </div>
          ) : (
            <canvas ref={lienzo} className="mx-auto block rounded-md bg-white " />
          )}
        </div>
      </div>
    </div>
  );
}

/** Columna de miniaturas: se dibujan una a una (hasta 80 páginas) para no bloquear el visor. */
function Miniaturas({
  documento,
  actual,
  alElegir,
}: {
  documento: pdfjs.PDFDocumentProxy;
  actual: number;
  alElegir: (n: number) => void;
}) {
  const lienzos = useRef<(HTMLCanvasElement | null)[]>([]);
  const n = Math.min(documento.numPages, 80);

  useEffect(() => {
    let vigente = true;
    (async () => {
      for (let i = 1; i <= n && vigente; i++) {
        const p = await documento.getPage(i);
        const canvas = lienzos.current[i - 1];
        if (!canvas || !vigente) continue;
        const base = p.getViewport({ scale: 1 });
        const viewport = p.getViewport({ scale: 96 / base.width });
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        await p.render({ canvas, viewport }).promise.catch(() => undefined);
      }
    })();
    return () => {
      vigente = false;
    };
  }, [documento, n]);

  return (
    <nav aria-label="Miniaturas de páginas" className="hidden w-32 shrink-0 space-y-3 overflow-y-auto border-r border-ink/8 p-3 md:block">
      {Array.from({ length: n }, (_, i) => (
        <button
          key={i}
          onClick={() => alElegir(i + 1)}
          aria-label={`Ir a la página ${i + 1}`}
          aria-current={actual === i + 1 ? "page" : undefined}
          className={cn(
            "block w-full rounded-lg border-2 p-0.5 transition-colors",
            actual === i + 1 ? "border-hema" : "border-transparent hover:border-ink/25",
          )}
        >
          <canvas ref={(el) => void (lienzos.current[i] = el)} className="w-full rounded bg-white" />
          <span className="num mt-1 block text-center text-[0.7rem] text-tx-3">{i + 1}</span>
        </button>
      ))}
    </nav>
  );
}

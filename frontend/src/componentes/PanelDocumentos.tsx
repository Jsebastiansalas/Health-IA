import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertOctagon,
  CheckCheck,
  Clock,
  FileText,
  Loader2,
  Trash2,
  TriangleAlert,
  UploadCloud,
} from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { api, subirPdf } from "../api/cliente";
import type { Documento, EstadoIndexacion, TipoDocumento } from "../api/tipos";
import { cn } from "../lib/cn";
import { esFinal, estadoPaso, etiquetaDocumento, fecha, PASOS, tamano, TIPOS_DOCUMENTO } from "../lib/formato";
import { Boton } from "./ui/Boton";
import { Esqueleto } from "./ui/Esqueleto";
import { Insignia } from "./ui/Insignia";

export function PanelDocumentos({ expedienteId, puedeSubir }: { expedienteId: string; puedeSubir: boolean }) {
  const { data: documentos, isLoading } = useQuery({
    queryKey: ["documentos", expedienteId],
    queryFn: () => api<Documento[]>(`/expedientes/${expedienteId}/documentos`),
    // Mientras haya documentos en proceso, el pipeline se actualiza solo.
    refetchInterval: (q) => (q.state.data?.some((d) => !esFinal(d.estado_indexacion)) ? 1500 : false),
  });

  return (
    <section aria-labelledby="titulo-folios">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 id="titulo-folios" className="text-xl font-semibold">
          Documentos
        </h2>
        <span className="num text-sm text-tinta-3">{documentos?.length ?? 0} cargados</span>
      </div>
      {puedeSubir && <FormularioSubida expedienteId={expedienteId} />}
      <ul className="mt-4 space-y-3">
        {isLoading && (
          <li aria-busy>
            <Esqueleto className="h-32 rounded-3xl" />
          </li>
        )}
        {documentos?.map((d) => <FilaDocumento key={d.id} doc={d} />)}
        {documentos?.length === 0 && (
          <li className="rounded-3xl border border-dashed border-tinta/14 p-6 text-sm leading-relaxed text-tinta-2">
            Aún no hay documentos. Sube el pliego y sus adendas desde tu equipo: el original no queda guardado en el
            servidor.
          </li>
        )}
      </ul>
    </section>
  );
}

function FormularioSubida({ expedienteId }: { expedienteId: string }) {
  const cliente = useQueryClient();
  const entrada = useRef<HTMLInputElement>(null);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [tipo, setTipo] = useState<TipoDocumento>("PLIEGO");
  const [numero, setNumero] = useState(1);
  const [progreso, setProgreso] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [arrastrando, setArrastrando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!archivo) return;
    const form = new FormData();
    form.append("tipo_documento", tipo);
    form.append("numero_adenda", tipo === "ADENDA" ? String(numero) : "0");
    form.append("archivo", archivo, archivo.name);
    setError(null);
    setProgreso(0);
    try {
      await subirPdf(expedienteId, form, setProgreso);
      toast.success("PDF recibido", { description: `${archivo.name}: ahora se valida e indexa.` });
      setArchivo(null);
      if (entrada.current) entrada.current.value = "";
      cliente.invalidateQueries({ queryKey: ["documentos", expedienteId] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cargar el PDF.");
    } finally {
      setProgreso(null);
    }
  }

  const subiendo = progreso !== null;
  return (
    <form onSubmit={enviar} className="vidrio space-y-4 rounded-3xl p-5">
      <label
        className={cn(
          "relative block cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed p-6 text-center transition-[border-color,background-color,transform] duration-300",
          arrastrando
            ? "scale-[1.01] border-accion bg-accion/12"
            : archivo
              ? "border-accion/60 bg-accion/[0.07]"
              : "border-tinta/16 bg-mesa hover:border-accion/50 hover:bg-accion/[0.05]",
        )}
        onDragOver={(e) => {
          e.preventDefault();
          setArrastrando(true);
        }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={(e) => {
          e.preventDefault();
          setArrastrando(false);
          const f = e.dataTransfer.files[0];
          if (f) setArchivo(f);
        }}
      >
        <input
          ref={entrada}
          type="file"
          accept="application/pdf,.pdf"
          className="sr-only"
          onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
        />
        {archivo ? (
          <span className="flex items-center justify-center gap-3 text-left">
            <span className="grid size-11 place-items-center rounded-xl bg-accion/15 text-accion">
              <FileText className="size-6" strokeWidth={1.6} aria-hidden />
            </span>
            <span className="min-w-0">
              <span className="block truncate font-semibold">{archivo.name}</span>
              <span className="etiqueta">{tamano(archivo.size)} · listo para cargar</span>
            </span>
          </span>
        ) : (
          <span className="block">
            <UploadCloud
              className={cn("mx-auto size-9 text-accion transition-transform", arrastrando && "-translate-y-1")}
              strokeWidth={1.5}
              aria-hidden
            />
            <span className="mt-2 block font-medium">
              {arrastrando ? "Suelta el PDF aquí" : "Arrastra un PDF o elígelo en tu equipo"}
            </span>
            <span className="mt-1 block text-xs text-tinta-3">Se valida, se indexa y el original se elimina del servidor</span>
          </span>
        )}
      </label>

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[11rem] flex-1">
          <label htmlFor="tipo-doc" className="mb-1.5 block text-[0.8rem] font-medium text-tinta-2">
            Tipo de documento
          </label>
          <select
            id="tipo-doc"
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoDocumento)}
            className="h-11 w-full rounded-md border border-tinta/35 bg-folio px-5 text-sm outline-none transition-[border-color,box-shadow] focus:border-tinta"
          >
            {Object.entries(TIPOS_DOCUMENTO).map(([v, t]) => (
              <option key={v} value={v} className="bg-folio">
                {t}
              </option>
            ))}
          </select>
        </div>
        {tipo === "ADENDA" && (
          <div className="w-24">
            <label htmlFor="n-adenda" className="mb-1.5 block text-[0.8rem] font-medium text-tinta-2">
              N° adenda
            </label>
            <input
              id="n-adenda"
              type="number"
              min={1}
              max={999}
              value={numero}
              onChange={(e) => setNumero(Number(e.target.value))}
              className="num h-11 w-full rounded-md border border-tinta/35 bg-folio px-5 text-sm outline-none focus:border-tinta"
            />
          </div>
        )}
        <Boton type="submit" variante="primario" tamano="md" disabled={!archivo || subiendo} className="min-w-28">
          {subiendo ? <span className="num">{Math.round(progreso * 100)} %</span> : "Cargar"}
        </Boton>
      </div>

      {subiendo && (
        <div
          className="h-2 overflow-hidden rounded-full bg-tinta/10"
          role="progressbar"
          aria-label="Progreso de carga"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progreso * 100)}
        >
          <div
            className="h-full rounded-full bg-accion transition-[width] duration-200"
            style={{ width: `${progreso * 100}%` }}
          />
        </div>
      )}
      {error && (
        <p role="alert" className="flex items-start gap-2 rounded-xl border border-peligro/35 bg-peligro/10 px-3.5 py-3 text-sm text-peligro">
          <AlertOctagon className="mt-0.5 size-4 shrink-0 text-peligro" aria-hidden />
          {error}
        </p>
      )}
    </form>
  );
}

function FilaDocumento({ doc }: { doc: Documento }) {
  const error = doc.estado_indexacion === "ERROR_PURGADO";
  const pendientePurga = doc.estado_indexacion === "INDEXADO_PENDIENTE_PURGA";
  const listo = doc.estado_indexacion === "INDEXADO_Y_PURGADO";
  return (
    <li className="folio animate-aparecer p-4">
      <div className="flex items-start gap-3.5">
        <span
          className={cn(
            "grid size-11 shrink-0 place-items-center rounded-xl border",
            error ? "border-peligro/30 bg-peligro/10 text-peligro" : "border-accion/25 bg-accion/10 text-accion",
          )}
        >
          <FileText className="size-5" strokeWidth={1.6} aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[0.78rem] font-medium text-accion/90">
            {etiquetaDocumento(doc.tipo_documento, doc.numero_adenda)}
          </p>
          <p className="truncate font-semibold" title={doc.nombre_archivo_original}>
            {doc.nombre_archivo_original}
          </p>
          <p className="num mt-0.5 text-xs text-tinta-3" title={`SHA-256 ${doc.sha256_original}`}>
            {tamano(doc.tamano_bytes)}
            {doc.total_paginas ? ` · ${doc.total_paginas} págs.` : ""}
            {doc.total_chunks_esperados ? ` · ${doc.total_chunks_esperados} fragmentos` : ""} ·{" "}
            <span className="font-mono">{doc.sha256_original.slice(0, 10)}…</span>
          </p>
        </div>
        {listo && (
          <span className="inline-flex shrink-0 -rotate-2 items-center gap-1.5 rounded-[3px] border-2 border-accion/70 px-2 py-0.5 font-display text-[0.68rem] font-bold uppercase tracking-wider text-accion">
            <Trash2 className="size-3.5" aria-hidden />
            PDF eliminado
          </span>
        )}
        {error && (
          <Insignia tono="peligro" className="shrink-0">
            Rechazado
          </Insignia>
        )}
        {pendientePurga && (
          <Insignia tono="aviso" className="shrink-0">
            <Clock className="size-3.5" aria-hidden />
            Purga pendiente
          </Insignia>
        )}
      </div>

      {error ? (
        <p className="mt-4 flex items-start gap-2.5 rounded-xl border border-peligro/30 bg-peligro/10 px-3.5 py-3 text-sm text-peligro">
          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-peligro" aria-hidden />
          {doc.motivo_error}
        </p>
      ) : (
        <Pipeline estado={doc.estado_indexacion} progreso={doc.progreso} />
      )}

      {doc.purged_at && !error && (
        <p className="mt-3 flex items-center gap-2 text-xs text-tinta-2">
          <CheckCheck className="size-4 text-accion" aria-hidden />
          Copia temporal destruida el {fecha(doc.purged_at)}. El original permanece en tu equipo.
        </p>
      )}
      {pendientePurga && doc.purga_programada_at && (
        <p className="mt-3 text-xs text-aviso">
          Indexado. La copia temporal se destruirá el {fecha(doc.purga_programada_at)}.
        </p>
      )}
      {doc.aviso_ocr_desactualizado && (
        <p className="mt-3 rounded-xl border border-aviso/30 bg-aviso/10 px-3.5 py-2.5 text-xs leading-relaxed text-aviso">
          Este documento se leyó con un OCR anterior ({doc.ocr_version}). Vuelve a cargarlo desde tu equipo para mejorar
          la extracción de sus {doc.paginas_ocr} página(s) escaneadas.
        </p>
      )}
    </li>
  );
}

/**
 * Pipeline: una barra de seis tramos y UNA línea con la etapa actual en lenguaje completo. Antes eran
 * seis columnas con etiquetas truncadas («Texto y …») en un panel estrecho. La lista completa de
 * etapas sigue disponible para lectores de pantalla.
 */
function Pipeline({ estado, progreso }: { estado: EstadoIndexacion; progreso: number }) {
  const estados = PASOS.map((_, i) => estadoPaso(estado, i));
  const indiceActual = estados.indexOf("actual");
  const completo = estados.every((e) => e === "hecho");
  const mostrado = completo ? PASOS[PASOS.length - 1]! : PASOS[Math.max(indiceActual, 0)]!;
  const vectorizando = mostrado.estado === "VECTORIZANDO" && !completo;
  return (
    <div className="mt-4" role="group" aria-label={`Estado del proceso: ${mostrado.descripcion}`}>
      <div className="flex gap-1" aria-hidden>
        {estados.map((e, i) => (
          <span
            key={PASOS[i]!.estado}
            className={cn(
              "h-1.5 flex-1 rounded-[2px] transition-colors duration-500",
              e === "hecho" && "bg-accion",
              e === "actual" && "animate-pulse bg-accion/60",
              e === "pendiente" && "bg-tinta/12",
            )}
          />
        ))}
      </div>
      <p className="mt-2 flex items-center gap-2 text-[0.82rem] leading-snug text-tinta-2">
        {completo ? (
          <CheckCheck className="size-4 shrink-0 text-ok" aria-hidden />
        ) : (
          <Loader2 className="size-4 shrink-0 animate-spin text-accion" aria-hidden />
        )}
        <span className={cn(!completo && "text-tinta")}>
          {completo ? mostrado.descripcion : `Etapa ${indiceActual + 1} de ${PASOS.length} · ${mostrado.descripcion}`}
          {vectorizando && <span className="num ml-1.5 font-semibold text-accion">{progreso}%</span>}
        </span>
      </p>
      <ol className="sr-only">
        {PASOS.map((p, i) => (
          <li key={p.estado}>
            {p.descripcion}: {estados[i] === "hecho" ? "hecho" : estados[i] === "actual" ? "en curso" : "pendiente"}
          </li>
        ))}
      </ol>
    </div>
  );
}

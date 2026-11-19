import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { api, subirPdf } from "../api/cliente";
import type { Documento, TipoDocumento } from "../api/tipos";
import { esFinal, estadoPaso, etiquetaDocumento, fecha, PASOS, tamano, TIPOS_DOCUMENTO } from "../lib/formato";

export function PanelDocumentos({ expedienteId, puedeSubir }: { expedienteId: string; puedeSubir: boolean }) {
  const { data: documentos } = useQuery({
    queryKey: ["documentos", expedienteId],
    queryFn: () => api<Documento[]>(`/expedientes/${expedienteId}/documentos`),
    // Mientras haya documentos en proceso, la barra del pipeline se actualiza sola.
    refetchInterval: (q) => (q.state.data?.some((d) => !esFinal(d.estado_indexacion)) ? 1500 : false),
  });

  return (
    <section aria-labelledby="titulo-folios">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 id="titulo-folios" className="font-display text-2xl">Folios</h2>
        <span className="etiqueta">{documentos?.length ?? 0} documentos</span>
      </div>
      {puedeSubir && <FormularioSubida expedienteId={expedienteId} />}
      <ul className="mt-6 space-y-4">
        {documentos?.map((d) => <FilaDocumento key={d.id} doc={d} />)}
        {documentos?.length === 0 && (
          <li className="border border-dashed border-papel-3 p-6 text-sm text-tinta-2">
            Sin documentos. Cargue el pliego y sus adendas desde su computador: el original nunca queda guardado aquí.
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
      setArchivo(null);
      if (entrada.current) entrada.current.value = "";
      cliente.invalidateQueries({ queryKey: ["documentos", expedienteId] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cargar el PDF.");
    } finally {
      setProgreso(null);
    }
  }

  return (
    <form onSubmit={enviar} className="folio space-y-4 p-5">
      <label
        className={`block cursor-pointer border-2 border-dashed p-5 text-center transition-colors ${
          archivo ? "border-clinico bg-clinico-claro/40" : "border-papel-3 hover:border-tinta-2"
        }`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const f = e.dataTransfer.files[0];
          if (f) setArchivo(f);
        }}
      >
        <input ref={entrada} type="file" accept="application/pdf,.pdf" className="sr-only"
          onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
        {archivo ? (
          <span>
            <span className="block font-medium">{archivo.name}</span>
            <span className="etiqueta">{tamano(archivo.size)}</span>
          </span>
        ) : (
          <span className="text-sm text-tinta-2">
            Arrastre un PDF o <span className="underline decoration-sello underline-offset-2">elíjalo en su PC</span>
          </span>
        )}
      </label>
      <div className="flex items-end gap-3">
        <label className="flex-1">
          <span className="etiqueta">Tipo</span>
          <select className="campo" value={tipo} onChange={(e) => setTipo(e.target.value as TipoDocumento)}>
            {Object.entries(TIPOS_DOCUMENTO).map(([v, t]) => (
              <option key={v} value={v}>{t}</option>
            ))}
          </select>
        </label>
        {tipo === "ADENDA" && (
          <label className="w-20">
            <span className="etiqueta">N°</span>
            <input className="campo font-mono" type="number" min={1} max={999} value={numero}
              onChange={(e) => setNumero(Number(e.target.value))} />
          </label>
        )}
        <button className="boton boton-tinta" disabled={!archivo || progreso !== null}>
          {progreso !== null ? `${Math.round(progreso * 100)} %` : "Cargar"}
        </button>
      </div>
      {progreso !== null && (
        <div className="h-1 bg-papel-3" aria-label="Progreso de carga">
          <div className="h-full bg-tinta transition-[width]" style={{ width: `${progreso * 100}%` }} />
        </div>
      )}
      {error && <p role="alert" className="text-sm text-sello">{error}</p>}
    </form>
  );
}

function FilaDocumento({ doc }: { doc: Documento }) {
  const error = doc.estado_indexacion === "ERROR_PURGADO";
  const pendientePurga = doc.estado_indexacion === "INDEXADO_PENDIENTE_PURGA";
  return (
    <li className="folio animate-aparecer p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="etiqueta">{etiquetaDocumento(doc.tipo_documento, doc.numero_adenda)}</p>
          <p className="truncate font-medium" title={doc.nombre_archivo_original}>{doc.nombre_archivo_original}</p>
          <p className="mt-0.5 font-mono text-[0.68rem] text-grafito" title={`SHA-256 ${doc.sha256_original}`}>
            {tamano(doc.tamano_bytes)}
            {doc.total_paginas ? ` · ${doc.total_paginas} págs.` : ""}
            {doc.total_chunks_esperados ? ` · ${doc.total_chunks_esperados} fragmentos` : ""} · {doc.sha256_original.slice(0, 12)}…
          </p>
        </div>
        {doc.estado_indexacion === "INDEXADO_Y_PURGADO" && (
          <span className="sello shrink-0 animate-estampar text-clinico">PDF eliminado</span>
        )}
        {error && <span className="sello shrink-0 animate-estampar text-sello">Rechazado</span>}
      </div>

      {error ? (
        <p className="mt-3 border-l-2 border-sello pl-3 text-sm text-sello">{doc.motivo_error}</p>
      ) : (
        <LineaPipeline doc={doc} />
      )}

      {doc.purged_at && !error && (
        <p className="mt-3 text-xs text-tinta-2">
          Copia temporal destruida el {fecha(doc.purged_at)}. El original permanece en su PC.
        </p>
      )}
      {pendientePurga && doc.purga_programada_at && (
        <p className="mt-3 text-xs text-ambar">Indexado. La copia temporal se destruirá el {fecha(doc.purga_programada_at)}.</p>
      )}
      {doc.aviso_ocr_desactualizado && (
        <p className="mt-3 bg-ambar-claro px-3 py-2 text-xs text-ambar">
          Este documento se leyó con un OCR anterior ({doc.ocr_version}). Vuelva a cargarlo desde su PC para mejorar
          la extracción de sus {doc.paginas_ocr} página(s) escaneadas.
        </p>
      )}
    </li>
  );
}

function LineaPipeline({ doc }: { doc: Documento }) {
  return (
    <ol className="mt-4 grid grid-cols-6 gap-1" aria-label={`Estado: ${doc.estado_indexacion}`}>
      {PASOS.map((paso, i) => {
        const estado = estadoPaso(doc.estado_indexacion, i);
        return (
          <li key={paso.estado} className="min-w-0">
            <div
              className={`h-1.5 ${
                estado === "hecho" ? "bg-clinico" : estado === "actual" ? "animate-pulse bg-tinta" : "bg-papel-3"
              }`}
            />
            <p className={`mt-1.5 text-[0.62rem] leading-tight ${estado === "pendiente" ? "text-grafito" : "text-tinta"}`}>
              {paso.etiqueta}
              {paso.estado === "VECTORIZANDO" && estado === "actual" && ` ${doc.progreso}%`}
            </p>
          </li>
        );
      })}
    </ol>
  );
}

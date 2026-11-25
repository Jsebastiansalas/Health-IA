import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertOctagon,
  Camera,
  CheckCheck,
  Clock,
  FileText,
  Loader2,
  Pill,
  CalendarBlank,
  ScrollText,
  Trash2,
  TriangleAlert,
  UploadCloud,
} from "../iconos";
import { useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { api, post, subirDocumento } from "../api/cliente";
import { useArmarLineaDeTiempo } from "../lib/lineaDeTiempo";
import type { Documento, EstadoIndexacion, RespuestaConsulta, TipoDocumento } from "../api/tipos";
import { cn } from "../lib/cn";
import { esFinal, estadoPaso, etiquetaDocumento, fecha, PASOS, tamano, TIPOS_DOCUMENTO } from "../lib/formato";
import { Boton } from "./ui/Boton";
import { Esqueleto } from "./ui/Esqueleto";
import { Insignia } from "./ui/Insignia";

export function PanelDocumentos({
  expedienteId,
  puedeSubir,
  puedeExplicar = true,
  alExplicar,
  clinico = false,
}: {
  expedienteId: string;
  puedeSubir: boolean;
  /** Falso mientras la persona no haya aceptado el consentimiento. */
  puedeExplicar?: boolean;
  /** Se llama cuando la explicación ya está lista, para llevar a la persona a la consola. */
  alExplicar?: () => void;
  /** Expediente clínico o cuenta personal: el tipo por defecto es «Historia clínica», no «Pliego». */
  clinico?: boolean;
}) {
  const cliente = useQueryClient();
  const linea = useArmarLineaDeTiempo(expedienteId, alExplicar);
  const cruce = useMutation({
    mutationFn: () => post<RespuestaConsulta>(`/expedientes/${expedienteId}/medicamentos/cruce`, {}),
    onSuccess: (r) => {
      cliente.setQueryData<RespuestaConsulta[]>(["consultas", expedienteId], (h) => [r, ...(h ?? [])]);
      alExplicar?.();
    },
  });
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
        <span className="num text-sm text-texto-3">{documentos?.length ?? 0} cargados</span>
      </div>
      {puedeSubir && <FormularioSubida expedienteId={expedienteId} clinico={clinico} />}
      {documentos?.some((d) => d.estado_indexacion === "INDEXADO_Y_PURGADO" || d.estado_indexacion === "INDEXADO_PENDIENTE_PURGA") && (
        <div className="mt-4">
          <Boton variante="secundario" tamano="sm" onClick={() => cruce.mutate()} disabled={!puedeExplicar} cargando={cruce.isPending}>
            {!cruce.isPending && <Pill className="size-4" aria-hidden />}
            {cruce.isPending ? "Revisando tus medicamentos…" : "Ver advertencias de mis medicamentos"}
          </Boton>
          <p className="mt-2 text-xs text-texto-3">Cruza los medicamentos de tus documentos con sus fichas técnicas. No indica qué tomar.</p>
          {cruce.error && (
            <p role="alert" className="mt-2 text-sm text-peligro">
              {(cruce.error as Error).message}
            </p>
          )}
          <Boton
            variante="secundario"
            tamano="sm"
            className="mt-4"
            onClick={() => linea.mutate(false)}
            disabled={!puedeExplicar}
            cargando={linea.isPending}
          >
            {!linea.isPending && <CalendarBlank className="size-4" aria-hidden />}
            {linea.isPending ? "Ordenando tus documentos…" : "Ver mi línea de tiempo"}
          </Boton>
          <p className="mt-2 text-xs text-texto-3">
            Ordena por fecha lo que dicen tus documentos y cómo cambiaron tus exámenes. No interpreta resultados.
          </p>
          {linea.error && (
            <p role="alert" className="mt-2 text-sm text-peligro">
              {(linea.error as Error).message}
            </p>
          )}
        </div>
      )}
      <ul className="mt-4 space-y-3">
        {isLoading && (
          <li aria-busy>
            <Esqueleto className="h-32 rounded-xl" />
          </li>
        )}
        {documentos?.map((d) => (
          <FilaDocumento key={d.id} doc={d} expedienteId={expedienteId} puedeExplicar={puedeExplicar} alExplicar={alExplicar} />
        ))}
        {documentos?.length === 0 && (
          <li className="rounded-xl border border-dashed border-borde p-6 text-sm leading-relaxed text-texto-2">
            Aún no hay documentos. Sube el pliego y sus adendas desde tu equipo: el original no queda guardado en el
            servidor.
          </li>
        )}
      </ul>
    </section>
  );
}

/** Formulario de carga. `archivoInicial` llega ya elegido (p. ej. desde «Compartir»); `alSubir` avisa al terminar. */
export function FormularioSubida({
  expedienteId,
  clinico,
  archivoInicial,
  alSubir,
}: {
  expedienteId: string;
  clinico: boolean;
  archivoInicial?: File | null;
  alSubir?: () => void;
}) {
  const cliente = useQueryClient();
  const entrada = useRef<HTMLInputElement>(null);
  const camara = useRef<HTMLInputElement>(null);
  const [archivo, setArchivo] = useState<File | null>(archivoInicial ?? null);
  const [tipo, setTipo] = useState<TipoDocumento>(clinico ? "HISTORIA_CLINICA" : "PLIEGO");
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
      await subirDocumento(expedienteId, form, setProgreso);
      toast.success("Documento recibido", { description: `${archivo.name}: ahora se valida e indexa.` });
      setArchivo(null);
      if (entrada.current) entrada.current.value = "";
      cliente.invalidateQueries({ queryKey: ["documentos", expedienteId] });
      alSubir?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cargar el documento.");
    } finally {
      setProgreso(null);
    }
  }

  const subiendo = progreso !== null;
  return (
    <form id="subida-documento" onSubmit={enviar} className="panel space-y-4 p-4">
      <label
        className={cn(
          "relative block cursor-pointer overflow-hidden rounded-xl border-2 border-dashed p-6 text-center transition-[border-color,background-color,transform] duration-300",
          arrastrando
            ? "scale-[1.01] border-primario bg-primario/12"
            : archivo
              ? "border-primario/60 bg-primario/[0.07]"
              : "border-borde bg-fondo hover:border-primario/50 hover:bg-primario/[0.05]",
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
          accept="application/pdf,image/jpeg,image/png,image/heic,image/heif,.pdf,.jpg,.jpeg,.png,.heic,.heif"
          className="sr-only"
          onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
        />
        {archivo ? (
          <span className="flex items-center justify-center gap-3 text-left">
            <span className="grid size-10 place-items-center rounded-xl bg-primario/15 text-primario">
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
              className={cn("mx-auto size-8 text-primario transition-transform", arrastrando && "-translate-y-1")}
              strokeWidth={1.5}
              aria-hidden
            />
            <span className="mt-2 block font-medium">
              {arrastrando ? "Suelta el documento aquí" : "Arrastra un PDF o una foto, o elígelo en tu equipo"}
            </span>
            <span className="mt-1 block text-xs text-texto-3">PDF, JPG, PNG o HEIC. Se lee, se indexa y el original se elimina del servidor</span>
          </span>
        )}
      </label>

      {/* En el móvil, abre la cámara directamente: es la forma natural de subir el papel que te dieron. */}
      <div className="hidden pointer-coarse:block">
        <input
          ref={camara}
          type="file"
          accept="image/*"
          capture="environment"
          className="sr-only"
          aria-label="Fotografiar un documento"
          onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
        />
        <Boton type="button" variante="secundario" className="w-full" onClick={() => camara.current?.click()}>
          <Camera className="size-4" aria-hidden />
          Tomar una foto del documento
        </Boton>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[11rem] flex-1">
          <label htmlFor="tipo-doc" className="mb-2 block text-xs font-medium text-texto-2">
            Tipo de documento
          </label>
          <select
            id="tipo-doc"
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoDocumento)}
            className="h-10 w-full rounded-lg border border-borde bg-panel px-4 text-sm outline-none transition-[border-color,box-shadow] focus:border-texto"
          >
            {Object.entries(TIPOS_DOCUMENTO).map(([v, t]) => (
              <option key={v} value={v} className="bg-panel">
                {t}
              </option>
            ))}
          </select>
        </div>
        {tipo === "ADENDA" && (
          <div className="w-24">
            <label htmlFor="n-adenda" className="mb-2 block text-xs font-medium text-texto-2">
              N° adenda
            </label>
            <input
              id="n-adenda"
              type="number"
              min={1}
              max={999}
              value={numero}
              onChange={(e) => setNumero(Number(e.target.value))}
              className="num h-10 w-full rounded-lg border border-borde bg-panel px-4 text-sm outline-none focus:border-texto"
            />
          </div>
        )}
        <Boton type="submit" variante="primario" tamano="md" disabled={!archivo || subiendo} className="min-w-28">
          {subiendo ? <span className="num">{Math.round(progreso * 100)} %</span> : "Cargar"}
        </Boton>
      </div>

      {subiendo && (
        <div
          className="h-2 overflow-hidden rounded-full bg-texto/10"
          role="progressbar"
          aria-label="Progreso de carga"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progreso * 100)}
        >
          <div
            className="h-full rounded-full bg-primario transition-[width] duration-200"
            style={{ width: `${progreso * 100}%` }}
          />
        </div>
      )}
      {error && (
        <p role="alert" className="flex items-start gap-2 rounded-xl border border-peligro/35 bg-peligro/10 px-4 py-3 text-sm text-peligro">
          <AlertOctagon className="mt-0.5 size-4 shrink-0 text-peligro" aria-hidden />
          {error}
        </p>
      )}
    </form>
  );
}

function FilaDocumento({
  doc,
  expedienteId,
  puedeExplicar,
  alExplicar,
}: {
  doc: Documento;
  expedienteId: string;
  puedeExplicar: boolean;
  alExplicar?: () => void;
}) {
  const cliente = useQueryClient();
  const explicar = useMutation({
    mutationFn: () => post<RespuestaConsulta>(`/expedientes/${expedienteId}/documentos/${doc.id}/explicacion`, {}),
    onSuccess: (r) => {
      cliente.setQueryData<RespuestaConsulta[]>(["consultas", expedienteId], (h) => [r, ...(h ?? [])]);
      alExplicar?.();
    },
  });
  const error = doc.estado_indexacion === "ERROR_PURGADO";
  const pendientePurga = doc.estado_indexacion === "INDEXADO_PENDIENTE_PURGA";
  const listo = doc.estado_indexacion === "INDEXADO_Y_PURGADO";
  return (
    <li className="panel animate-aparecer p-4">
      <div className="flex items-start gap-4">
        <span
          className={cn(
            "grid size-10 shrink-0 place-items-center rounded-xl border",
            error ? "border-peligro/30 bg-peligro/10 text-peligro" : "border-primario/25 bg-primario/10 text-primario",
          )}
        >
          <FileText className="size-5" strokeWidth={1.6} aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-primario/90">
            {etiquetaDocumento(doc.tipo_documento, doc.numero_adenda)}
          </p>
          <p className="truncate font-semibold" title={doc.nombre_archivo_original}>
            {doc.nombre_archivo_original}
          </p>
          <p className="num mt-0.5 text-xs text-texto-3" title={`SHA-256 ${doc.sha256_original}`}>
            {tamano(doc.tamano_bytes)}
            {doc.total_paginas ? ` · ${doc.total_paginas} págs.` : ""}
            {doc.total_chunks_esperados ? ` · ${doc.total_chunks_esperados} fragmentos` : ""} ·{" "}
            <span className="font-mono">{doc.sha256_original.slice(0, 10)}…</span>
          </p>
        </div>
        {listo && (
          <Insignia tono="ok" className="shrink-0">
            <Trash2 className="size-4" aria-hidden />
            Original eliminado
          </Insignia>
        )}
        {error && (
          <Insignia tono="peligro" className="shrink-0">
            Rechazado
          </Insignia>
        )}
        {pendientePurga && (
          <Insignia tono="aviso" className="shrink-0">
            <Clock className="size-4" aria-hidden />
            Purga pendiente
          </Insignia>
        )}
      </div>

      {error ? (
        <p className="mt-4 flex items-start gap-3 rounded-xl border border-peligro/30 bg-peligro/10 px-4 py-3 text-sm text-peligro">
          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-peligro" aria-hidden />
          {doc.motivo_error}
        </p>
      ) : (
        <Pipeline estado={doc.estado_indexacion} progreso={doc.progreso} />
      )}

      {doc.purged_at && !error && (
        <p className="mt-3 flex items-center gap-2 text-xs text-texto-2">
          <CheckCheck className="size-4 text-primario" aria-hidden />
          Copia temporal destruida el {fecha(doc.purged_at)}. El original permanece en tu equipo.
        </p>
      )}
      {pendientePurga && doc.purga_programada_at && (
        <p className="mt-3 text-xs text-aviso">
          Indexado. La copia temporal se destruirá el {fecha(doc.purga_programada_at)}.
        </p>
      )}
      {listo && (
        <div className="mt-4">
          <Boton
            tamano="sm"
            variante="secundario"
            onClick={() => explicar.mutate()}
            disabled={!puedeExplicar}
            cargando={explicar.isPending}
          >
            {!explicar.isPending && <ScrollText className="size-4" aria-hidden />}
            {explicar.isPending ? "Leyendo el documento…" : "Explícame este documento"}
          </Boton>
          {explicar.error && (
            <p role="alert" className="mt-2 text-sm text-peligro">
              {(explicar.error as Error).message}
            </p>
          )}
        </div>
      )}
      {doc.aviso_ocr_desactualizado && (
        <p className="mt-3 rounded-xl border border-aviso/30 bg-aviso/10 px-4 py-3 text-xs leading-relaxed text-aviso">
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
              "h-2 flex-1 rounded-sm transition-colors duration-500",
              e === "hecho" && "bg-primario",
              e === "actual" && "animate-pulse bg-primario/60",
              e === "pendiente" && "bg-texto/12",
            )}
          />
        ))}
      </div>
      <p className="mt-2 flex items-center gap-2 text-xs leading-snug text-texto-2">
        {completo ? (
          <CheckCheck className="size-4 shrink-0 text-ok" aria-hidden />
        ) : (
          <Loader2 className="size-4 shrink-0 animate-spin text-primario" aria-hidden />
        )}
        <span className={cn(!completo && "text-texto")}>
          {completo ? mostrado.descripcion : `Etapa ${indiceActual + 1} de ${PASOS.length} · ${mostrado.descripcion}`}
          {vectorizando && <span className="num ml-2 font-semibold text-primario">{progreso}%</span>}
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

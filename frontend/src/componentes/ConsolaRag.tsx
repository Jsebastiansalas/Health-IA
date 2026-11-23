import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertOctagon, ArrowUpRight, Check, Copy, CornerDownLeft, SendHorizontal, SearchX, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { toast } from "sonner";
import { api, post } from "../api/cliente";
import type { Cita, RespuestaConsulta } from "../api/tipos";
import { cn } from "../lib/cn";
import { Logotipo } from "./Marca";
import { TarjetaCita } from "./TarjetaCita";
import { AvisoSalud, AvisoUrgencia } from "./AvisoSalud";
import { ExplicacionDocumento } from "./ExplicacionDocumento";
import { Boton } from "./ui/Boton";
import { Esqueleto } from "./ui/Esqueleto";
import { Insignia } from "./ui/Insignia";

const SUGERENCIAS = [
  "¿Cuál es el plazo de entrega y alguna adenda lo modifica?",
  "¿Qué garantías y pólizas se exigen?",
  "¿Qué registros sanitarios INVIMA se acreditan?",
];

export function ConsolaRag({
  expedienteId,
  hayIndice,
  alAbrirCita,
  bloqueado = false,
}: {
  expedienteId: string;
  hayIndice: boolean;
  alAbrirCita: (c: Cita) => void;
  /** Hasta que la persona acepte el consentimiento no se puede consultar. */
  bloqueado?: boolean;
}) {
  const cliente = useQueryClient();
  const clave = ["consultas", expedienteId];
  const { data: historial } = useQuery({
    queryKey: clave,
    queryFn: () => api<RespuestaConsulta[]>(`/expedientes/${expedienteId}/consultas?limit=30`),
  });
  const [pregunta, setPregunta] = useState("");
  const [pendiente, setPendiente] = useState<string | null>(null);
  const fin = useRef<HTMLDivElement>(null);
  const campo = useRef<HTMLTextAreaElement>(null);

  const consultar = useMutation({
    mutationFn: (p: string) => post<RespuestaConsulta>(`/expedientes/${expedienteId}/consultas`, { pregunta: p }),
    onMutate: (p) => setPendiente(p),
    onSuccess: (r, p) => {
      cliente.setQueryData<RespuestaConsulta[]>(clave, (h) => [{ ...r, pregunta: p }, ...(h ?? [])]);
      setPregunta("");
    },
    onSettled: () => setPendiente(null),
  });

  const conversacion = [...(historial ?? [])].reverse();
  useEffect(() => {
    // Sin `return`: en Chrome recientes scrollIntoView devuelve una Promise y React la tomaría
    // como función de limpieza.
    fin.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [conversacion.length, pendiente]);

  function enviar(e: { preventDefault: () => void }) {
    e.preventDefault();
    const p = pregunta.trim();
    if (p.length >= 3 && !consultar.isPending) consultar.mutate(p);
  }

  const vacio = conversacion.length === 0 && !pendiente;
  return (
    <section aria-labelledby="titulo-consulta" className="flex min-h-[70vh] flex-col">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="titulo-consulta" className="text-2xl font-semibold">
          Consulta del expediente
        </h2>
        <span className="text-sm text-tinta-3">Respuestas solo con evidencia citada</span>
      </div>
      <AvisoSalud className="mb-5" />

      <div className="flex-1 space-y-8 pb-6" role="log" aria-live="polite" aria-label="Conversación">
        {vacio && (
          <div className="animate-aparecer">
            <p className="max-w-xl font-display text-2xl font-semibold leading-tight">
              {hayIndice ? "Pregunta lo que necesites del expediente." : "Aún no hay documentos indexados."}
            </p>
            <p className="mt-2 max-w-lg text-tinta-2">
              {hayIndice
                ? "Cada respuesta cita documento, página y sección. Si la evidencia no alcanza, el sistema lo dice."
                : "Sube un documento (PDF o foto) y espera a que termine el proceso: cuando el original se elimine del servidor, podrás consultarlo aquí."}
            </p>
            {hayIndice && (
              <ul className="mt-5 max-w-xl divide-y divide-tinta/12 border-y border-tinta/12">
                {SUGERENCIAS.map((q) => (
                  <li key={q}>
                    <button
                      onClick={() => {
                        setPregunta(q);
                        campo.current?.focus();
                      }}
                      className="group flex w-full items-center justify-between gap-4 py-3 text-left text-[0.95rem] text-tinta-2 transition-colors hover:text-tinta"
                    >
                      {q}
                      <ArrowUpRight className="size-4 shrink-0 text-tinta-3 transition-colors group-hover:text-accion" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {conversacion.map((r) => (
          <Intercambio key={r.consultaId} respuesta={r} alAbrirCita={alAbrirCita} />
        ))}

        {pendiente && (
          <div className="space-y-5 animate-aparecer">
            <Burbuja texto={pendiente} />
            <div className="flex gap-3.5" aria-busy aria-label="Analizando el expediente">
              <AvatarIA />
              <div className="folio flex-1 p-5">
                <p className="mb-4 text-sm font-medium text-accion">Analizando el expediente…</p>
                <div className="space-y-2.5">
                  <Esqueleto className="h-3.5 w-[92%]" />
                  <Esqueleto className="h-3.5 w-[78%]" />
                  <Esqueleto className="h-3.5 w-[55%]" />
                </div>
              </div>
            </div>
          </div>
        )}
        {consultar.error && (
          <p role="alert" className="flex items-start gap-2.5 rounded-2xl border border-peligro/35 bg-peligro/10 px-4 py-3 text-sm text-peligro">
            <AlertOctagon className="mt-0.5 size-4 shrink-0 text-peligro" aria-hidden />
            {(consultar.error as Error).message}
          </p>
        )}
        <div ref={fin} />
      </div>

      <form
        onSubmit={enviar}
        className="folio sticky bottom-4 z-10 p-2.5"
      >
        <div className="flex items-end gap-2.5">
          <textarea
            ref={campo}
            className="max-h-40 min-h-[2.9rem] flex-1 resize-none bg-transparent px-3 py-3 text-[0.95rem] outline-none disabled:cursor-not-allowed"
            rows={2}
            maxLength={2000}
            aria-label="Tu pregunta"
            placeholder={
              hayIndice
                ? "Ej.: ¿Qué requisitos técnicos exige la ficha del equipo de rayos X?"
                : "Carga un documento y espera la indexación"
            }
            disabled={!hayIndice || bloqueado}
            value={pregunta}
            onChange={(e) => setPregunta(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) enviar(e);
            }}
          />
          <Boton
            type="submit"
            variante="primario"
            tamano="icono"
            className="size-11 shrink-0"
            disabled={!hayIndice || bloqueado || pregunta.trim().length < 3}
            cargando={consultar.isPending}
            aria-label="Consultar"
          >
            {!consultar.isPending && <SendHorizontal className="size-[1.15rem]" aria-hidden />}
          </Boton>
        </div>
        <p className="mt-1 flex items-center gap-1.5 px-3 text-[0.72rem] text-tinta-3">
          <CornerDownLeft className="size-3" aria-hidden />
          Enter envía · Mayús + Enter salto de línea
        </p>
      </form>
    </section>
  );
}

function AvatarIA() {
  return (
    <span className="mt-1 grid size-9 shrink-0 place-items-center rounded-xl border border-accion/25 bg-mesa">
      <Logotipo className="size-6" />
    </span>
  );
}

function Burbuja({ texto }: { texto: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] rounded-md bg-folio-2 px-5 py-3 text-[0.97rem] leading-relaxed text-tinta">
        {texto}
      </p>
    </div>
  );
}

/** Convierte las referencias [n] del texto en enlaces a su tarjeta de cita (solo si esa cita existe). */
function conReferencias(texto: string, total: number) {
  return texto.replace(/\[(\d{1,2})\]/g, (m, n) => (Number(n) >= 1 && Number(n) <= total ? `[${n}](#cita-${n})` : m));
}

function Intercambio({ respuesta: r, alAbrirCita }: { respuesta: RespuestaConsulta; alAbrirCita: (c: Cita) => void }) {
  const [resaltada, setResaltada] = useState<number | null>(null);
  const [copiado, setCopiado] = useState(false);
  const base = `cita-${r.consultaId}`;

  function irACita(n: number) {
    setResaltada(n);
    document.getElementById(`${base}-${n}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => setResaltada(null), 2200);
  }

  async function copiar() {
    try {
      await navigator.clipboard.writeText(r.respuestaAnalitica);
      setCopiado(true);
      toast.success("Respuesta copiada");
      window.setTimeout(() => setCopiado(false), 1800);
    } catch {
      toast.error("No se pudo copiar la respuesta");
    }
  }

  return (
    <article className="space-y-5 animate-aparecer">
      <Burbuja texto={r.modo === "explicar" ? "Explícame este documento" : (r.pregunta ?? "")} />
      <div className="flex gap-3.5">
        <AvatarIA />
        <div className="min-w-0 flex-1">
          <div className={cn("folio p-5 sm:p-6", r.sinEvidencia && "border-aviso/30")}>
            {r.urgencia && <AvisoUrgencia mensaje={r.urgencia.mensaje} />}
            {r.modo === "explicar" ? (
              <ExplicacionDocumento respuesta={r} alIrACita={irACita} />
            ) : (
              <>
            {r.sinEvidencia && (
              <Insignia tono="aviso" className="mb-3.5">
                <SearchX className="size-3.5" aria-hidden />
                Sin evidencia suficiente
              </Insignia>
            )}
            <div className="space-y-3 text-[0.98rem] leading-relaxed [&_li]:ml-5 [&_li]:list-disc [&_strong]:font-semibold [&_strong]:text-tinta">
              <ReactMarkdown
                components={{
                  a: ({ href, children }) => {
                    const n = Number(href?.replace("#cita-", ""));
                    return (
                      <button
                        type="button"
                        onClick={() => irACita(n)}
                        className="mx-0.5 inline-grid size-5 -translate-y-0.5 place-items-center rounded-md bg-marca align-middle text-[0.7rem] font-bold text-marca-tx transition-colors hover:bg-accion hover:text-accion-tx"
                        aria-label={`Ir a la cita ${n}`}
                      >
                        {children}
                      </button>
                    );
                  },
                }}
              >
                {conReferencias(r.respuestaAnalitica, r.citas.length)}
              </ReactMarkdown>
            </div>
              </>
            )}

            {r.alertas.length > 0 && (
              <ul className="mt-5 space-y-2">
                {r.alertas.map((a) => (
                  <li
                    key={a}
                    className="flex gap-2.5 rounded-xl border border-aviso/30 bg-aviso/10 px-3.5 py-2.5 text-sm text-aviso"
                  >
                    <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                    <span>{a}</span>
                  </li>
                ))}
              </ul>
            )}

            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-tinta/8 pt-3.5">
              <p className="font-mono text-[0.7rem] leading-relaxed text-tinta-3">
                {r.fragmentosRecuperados} fragmentos recuperados · {r.modeloEmbeddings}
                {r.modeloLlm ? ` · ${r.modeloLlm}` : ""} · {(r.latenciaMs / 1000).toFixed(1)} s
              </p>
              <Boton tamano="sm" variante="fantasma" onClick={copiar}>
                {copiado ? <Check className="size-4 text-accion" aria-hidden /> : <Copy className="size-4" aria-hidden />}
                {copiado ? "Copiada" : "Copiar"}
              </Boton>
            </div>
          </div>

          {r.citas.length > 0 && (
            <div className="mt-4 grid grid-cols-[minmax(0,1fr)] gap-3 2xl:grid-cols-2">
              {r.citas.map((c, i) => (
                <TarjetaCita
                  key={`${c.documentoId}-${c.orden}-${i}`}
                  id={`${base}-${i + 1}`}
                  cita={c}
                  numero={i + 1}
                  resaltada={resaltada === i + 1}
                  alAbrir={alAbrirCita}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

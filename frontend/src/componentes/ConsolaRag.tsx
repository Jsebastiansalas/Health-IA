import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, post } from "../api/cliente";
import type { Cita, RespuestaConsulta } from "../api/tipos";
import { TarjetaCita } from "./TarjetaCita";

const SUGERENCIAS = [
  "¿Cuál es el plazo de entrega y alguna adenda lo modifica?",
  "¿Qué garantías y pólizas se exigen?",
  "¿Qué registros sanitarios INVIMA se acreditan?",
];

export function ConsolaRag({
  expedienteId,
  hayIndice,
  alAbrirCita,
}: {
  expedienteId: string;
  hayIndice: boolean;
  alAbrirCita: (c: Cita) => void;
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

  function enviar(e: FormEvent) {
    e.preventDefault();
    const p = pregunta.trim();
    if (p.length >= 3 && !consultar.isPending) consultar.mutate(p);
  }

  return (
    <section aria-labelledby="titulo-consulta" className="flex min-h-[70vh] flex-col">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 id="titulo-consulta" className="font-display text-2xl">Consulta del expediente</h2>
        <span className="etiqueta">Respuestas solo con evidencia citada</span>
      </div>

      <div className="flex-1 space-y-10 pb-6">
        {conversacion.length === 0 && !pendiente && (
          <div className="border border-dashed border-papel-3 p-8">
            <p className="font-display text-xl">
              {hayIndice ? "Pregunte lo que necesite del expediente." : "Aún no hay documentos indexados."}
            </p>
            <p className="mt-2 text-sm text-tinta-2">
              Cada respuesta cita documento, página y sección. Si la evidencia no alcanza, el sistema lo dice.
            </p>
            {hayIndice && (
              <div className="mt-5 flex flex-wrap gap-2">
                {SUGERENCIAS.map((s) => (
                  <button key={s} className="boton boton-linea !py-1.5 text-xs font-normal" onClick={() => setPregunta(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {conversacion.map((r) => (
          <Intercambio key={r.consultaId} respuesta={r} alAbrirCita={alAbrirCita} />
        ))}

        {pendiente && (
          <div className="animate-aparecer">
            <p className="font-display text-xl">{pendiente}</p>
            <p className="etiqueta mt-4 animate-pulse">Recuperando fragmentos y redactando con citas…</p>
          </div>
        )}
        {consultar.error && (
          <p role="alert" className="border-l-2 border-sello bg-sello-claro px-3 py-2 text-sm text-sello">
            {(consultar.error as Error).message}
          </p>
        )}
        <div ref={fin} />
      </div>

      <form onSubmit={enviar} className="sticky bottom-4 folio flex items-end gap-3 p-3">
        <textarea
          className="min-h-[2.75rem] flex-1 resize-none bg-transparent px-2 py-2 text-[0.95rem] outline-none"
          rows={2}
          maxLength={2000}
          placeholder={hayIndice ? "Ej.: ¿Qué requisitos técnicos exige la ficha del equipo de rayos X?" : "Cargue y espere la indexación de un documento"}
          disabled={!hayIndice}
          value={pregunta}
          onChange={(e) => setPregunta(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) enviar(e);
          }}
        />
        <button className="boton boton-tinta" disabled={!hayIndice || pregunta.trim().length < 3 || consultar.isPending}>
          Consultar
        </button>
      </form>
    </section>
  );
}

function Intercambio({ respuesta: r, alAbrirCita }: { respuesta: RespuestaConsulta; alAbrirCita: (c: Cita) => void }) {
  return (
    <article className="animate-aparecer">
      <p className="font-display text-xl leading-snug">{r.pregunta}</p>
      <div className={`mt-4 border-l-2 pl-5 ${r.sinEvidencia ? "border-ambar" : "border-tinta"}`}>
        {r.sinEvidencia && <span className="sello mb-3 text-ambar">Sin evidencia suficiente</span>}
        <div className="space-y-3 whitespace-pre-line text-[0.97rem] leading-relaxed">{r.respuestaAnalitica}</div>

        {r.alertas.length > 0 && (
          <ul className="mt-5 space-y-2">
            {r.alertas.map((a) => (
              <li key={a} className="flex gap-3 bg-sello-claro px-3 py-2 text-sm text-sello">
                <span aria-hidden className="font-mono font-bold">!</span>
                <span>{a}</span>
              </li>
            ))}
          </ul>
        )}

        {r.citas.length > 0 && (
          <div className="mt-6 grid gap-3 xl:grid-cols-2">
            {r.citas.map((c, i) => (
              <TarjetaCita key={`${c.documentoId}-${c.orden}-${i}`} cita={c} numero={i + 1} alAbrir={alAbrirCita} />
            ))}
          </div>
        )}
        <p className="mt-4 font-mono text-[0.62rem] text-grafito">
          {r.fragmentosRecuperados} fragmentos recuperados · {r.modeloEmbeddings}
          {r.modeloLlm ? ` · ${r.modeloLlm}` : ""} · {(r.latenciaMs / 1000).toFixed(1)} s
        </p>
      </div>
    </article>
  );
}

import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertOctagon, ExternalLink, Pill, SearchX, SendHorizontal, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api, post } from "../api/cliente";
import type { CitaAgregada, CitaMedicamento, CitaPrecio, CitaRegistro, FuenteCargada, RespuestaMedicamentos } from "../api/tipos";
import { Boton } from "../componentes/ui/Boton";
import { Esqueleto } from "../componentes/ui/Esqueleto";
import { Insignia } from "../componentes/ui/Insignia";
import { cn } from "../lib/cn";
import { fecha } from "../lib/formato";

const SUGERENCIAS = [
  "¿Qué registro sanitario y qué titular tiene el losartán potásico de 50 mg?",
  "Alternativas vigentes con acetaminofén 500 mg",
  "¿Cuál es el precio máximo regulado de la amoxicilina 500 mg?",
  "¿Qué laboratorios tienen registro vigente de metformina?",
];

const COP = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });
const plata = (v: string | null) => (v && !Number.isNaN(Number(v)) ? COP.format(Number(v)) : "—");

/** Fecha de un día (AAAA-MM-DD) sin corrimiento de zona horaria. INVIMA usa el año 3000 para «sin vencimiento». */
function dia(iso: string): string {
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  if (!a || !m || !d) return iso;
  if (a >= 2900) return "Sin vencimiento";
  return new Date(a, m - 1, d).toLocaleDateString("es-CO", { day: "2-digit", month: "short", year: "numeric" });
}

type Intercambio = { clave: string; pregunta: string; respuesta: RespuestaMedicamentos };

export function PaginaMedicamentos() {
  const [conversacion, setConversacion] = useState<Intercambio[]>([]);
  const [pregunta, setPregunta] = useState("");
  const [pendiente, setPendiente] = useState<string | null>(null);
  const fin = useRef<HTMLDivElement>(null);
  const campo = useRef<HTMLTextAreaElement>(null);

  const { data: fuentes } = useQuery({
    queryKey: ["medicamentos-fuentes"],
    queryFn: () => api<FuenteCargada[]>("/medicamentos/fuentes"),
  });
  const cargada = fuentes?.length ? fuentes.map((f) => f.cargadoAt).sort()[0] : null;

  const consultar = useMutation({
    mutationFn: (p: string) => post<RespuestaMedicamentos>("/medicamentos/consultas", { pregunta: p }),
    onMutate: (p) => setPendiente(p),
    onSuccess: (r, p) => {
      setConversacion((c) => [...c, { clave: r.consultaId, pregunta: p, respuesta: r }]);
      setPregunta("");
    },
    onSettled: () => setPendiente(null),
  });

  useEffect(() => {
    fin.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [conversacion.length, pendiente]);

  function enviar(e: { preventDefault: () => void }) {
    e.preventDefault();
    const p = pregunta.trim();
    if (p.length >= 3 && !consultar.isPending) consultar.mutate(p);
  }

  const vacio = conversacion.length === 0 && !pendiente;
  return (
    <section aria-labelledby="titulo-med" className="mx-auto flex min-h-[78vh] max-w-4xl flex-col">
      <header className="mb-8">
        <h1 id="titulo-med" className="text-4xl sm:text-5xl">
          Medicamentos
        </h1>
        <p className="mt-3 max-w-2xl text-tx-2">
          Pregunta por cualquier medicamento con registro en Colombia: titular, registro sanitario, vigencia, presentaciones,
          equivalentes y precio máximo regulado. Cada dato lleva su fuente.
        </p>
        <p className="etiqueta mt-3">
          {cargada
            ? `Datos de INVIMA (datos.gov.co, CC BY-SA 4.0) · cargados el ${fecha(cargada)}`
            : fuentes
              ? "La base de INVIMA aún no está cargada"
              : "Consultando fuentes…"}
        </p>
      </header>

      <div className="flex-1 space-y-8 pb-6" role="log" aria-live="polite" aria-label="Conversación">
        {vacio && (
          <div className="vidrio rounded-xl p-8">
            <Pill className="size-7 text-tx-2" strokeWidth={1.5} aria-hidden />
            <p className="mt-4 max-w-md font-display text-2xl leading-tight [font-stretch:112%]">Pregunta por un medicamento.</p>
            <p className="mt-3 max-w-lg text-tx-2">
              Responde con la base oficial de INVIMA. Dosis, indicaciones e interacciones no están en esa fuente: para eso, consulta
              la ficha técnica o el prospecto.
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              {SUGERENCIAS.map((s) => (
                <button
                  key={s}
                  onClick={() => {
                    setPregunta(s);
                    campo.current?.focus();
                  }}
                  className="rounded-full border border-ink/25 px-4 py-2 text-left text-[0.84rem] text-tx-2 transition-colors hover:border-ink/60 hover:text-tx"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {conversacion.map((c) => (
          <Respuesta key={c.clave} pregunta={c.pregunta} r={c.respuesta} />
        ))}

        {pendiente && (
          <div className="animate-aparecer space-y-5">
            <Burbuja texto={pendiente} />
            <div className="vidrio rounded-xl p-5" aria-busy aria-label="Consultando la base de INVIMA">
              <p className="mb-4 text-sm text-tx-2">Consultando la base de INVIMA…</p>
              <div className="space-y-2.5">
                <Esqueleto className="h-3.5 w-[92%]" />
                <Esqueleto className="h-3.5 w-[74%]" />
                <Esqueleto className="h-3.5 w-[50%]" />
              </div>
            </div>
          </div>
        )}
        {consultar.error && (
          <p role="alert" className="flex items-start gap-2.5 rounded-xl border border-coral/40 bg-coral/10 px-4 py-3 text-sm text-coral">
            <AlertOctagon className="mt-0.5 size-4 shrink-0" aria-hidden />
            {(consultar.error as Error).message}
          </p>
        )}
        <div ref={fin} />
      </div>

      <form onSubmit={enviar} className="vidrio sticky bottom-4 z-10 rounded-xl p-2.5">
        <div className="flex items-end gap-2.5">
          <textarea
            ref={campo}
            className="max-h-40 min-h-[2.9rem] flex-1 resize-none bg-transparent px-3 py-3 text-[0.95rem] outline-none"
            rows={2}
            maxLength={1000}
            aria-label="Tu pregunta sobre un medicamento"
            placeholder="Ej.: ¿Está vigente el registro de la losartán potásica de Genfar?"
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
            disabled={pregunta.trim().length < 3}
            cargando={consultar.isPending}
            aria-label="Consultar"
          >
            {!consultar.isPending && <SendHorizontal className="size-[1.15rem]" aria-hidden />}
          </Boton>
        </div>
      </form>
    </section>
  );
}

function Burbuja({ texto }: { texto: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] rounded-2xl rounded-tr-md bg-obsidiana px-5 py-3 text-[0.97rem] leading-relaxed text-tx">{texto}</p>
    </div>
  );
}

/** Convierte las referencias [R1], [P1], [E1] del texto en enlaces a su tarjeta (solo si esa cita existe). */
function conReferencias(texto: string, ids: Set<string>) {
  return texto.replace(/\[([RPE]\d{1,2})\]/g, (m, id) => (ids.has(id) ? `[${id}](#cita-${id})` : m));
}

function Respuesta({ pregunta, r }: { pregunta: string; r: RespuestaMedicamentos }) {
  const [resaltada, setResaltada] = useState<string | null>(null);
  const base = `cita-${r.consultaId}`;
  const ids = new Set(r.citas.map((c) => c.id));

  function irA(id: string) {
    setResaltada(id);
    document.getElementById(`${base}-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => setResaltada(null), 2200);
  }

  return (
    <article className="animate-aparecer space-y-5">
      <Burbuja texto={pregunta} />
      <div className="vidrio rounded-xl p-5 sm:p-6">
        {r.sinEvidencia && (
          <Insignia tono="ambar" className="mb-3.5">
            <SearchX className="size-3.5" aria-hidden />
            Sin evidencia suficiente
          </Insignia>
        )}
        <div className="space-y-3 text-[0.98rem] leading-relaxed [&_li]:ml-5 [&_li]:list-disc [&_strong]:font-medium [&_strong]:text-ink">
          <ReactMarkdown
            components={{
              a: ({ href, children }) => {
                const id = (href ?? "").replace("#cita-", "");
                return (
                  <button
                    type="button"
                    onClick={() => irA(id)}
                    className="mx-0.5 inline-grid h-5 min-w-5 -translate-y-0.5 place-items-center rounded-full bg-ink px-1.5 align-middle text-[0.68rem] font-medium text-sala"
                    aria-label={`Ir a la fuente ${id}`}
                  >
                    {children}
                  </button>
                );
              },
            }}
          >
            {conReferencias(r.respuestaAnalitica, ids)}
          </ReactMarkdown>
        </div>

        {r.alertas.length > 0 && (
          <ul className="mt-5 space-y-2">
            {r.alertas.map((a) => (
              <li key={a} className="flex gap-2.5 rounded-xl border border-ambar/35 bg-ambar/10 px-3.5 py-2.5 text-sm text-ambar">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span>{a}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-5 border-t border-ink/10 pt-3.5 text-[0.74rem] leading-relaxed text-tx-3">{r.aviso}</p>
      </div>

      {r.citas.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2">
          {r.citas.map((c) => (
            <Fuente key={c.id} cita={c} id={`${base}-${c.id}`} resaltada={resaltada === c.id} />
          ))}
        </div>
      )}
    </article>
  );
}

function Dato({ k, v }: { k: string; v: string | null | undefined }) {
  if (!v) return null;
  return (
    <div className="flex justify-between gap-4 border-t border-ink/10 py-2 text-[0.82rem]">
      <dt className="shrink-0 text-tx-3">{k}</dt>
      <dd className="text-right">{v}</dd>
    </div>
  );
}

function Fuente({ cita, id, resaltada }: { cita: CitaMedicamento; id: string; resaltada: boolean }) {
  return (
    <article id={id} className={cn("vidrio-solido flex flex-col rounded-xl p-5 transition-[box-shadow] duration-500", resaltada && "ring-1 ring-ink/70")}>
      {cita.tipo === "REGISTRO_INVIMA" && <TarjetaRegistro c={cita} />}
      {cita.tipo === "PRECIO_REGULADO" && <TarjetaPrecio c={cita} />}
      {cita.tipo === "CONSULTA_AGREGADA" && <TarjetaAgregada c={cita} />}
      <footer className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-ink/10 pt-3 text-[0.7rem] text-tx-3">
        <span>
          {cita.fuente.conjunto}
          {cita.fuente.cargadoAt ? ` · cargado el ${fecha(cita.fuente.cargadoAt)}` : ""}
        </span>
        <a
          href={cita.fuente.enlace}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-tx-2 underline underline-offset-4 hover:text-tx"
        >
          Ver fuente
          <ExternalLink className="size-3" aria-hidden />
        </a>
      </footer>
    </article>
  );
}

const ESTADO_TONO: Record<CitaRegistro["conjunto"], "ok" | "ambar" | "coral" | "neutro"> = {
  VIGENTE: "ok",
  RENOVACION: "ambar",
  OTROS: "neutro",
  VENCIDO: "coral",
};

function TarjetaRegistro({ c }: { c: CitaRegistro }) {
  return (
    <>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="etiqueta">{c.id} · CUM {c.cum}</p>
          <h3 className="mt-1 break-words text-[1.1rem]">{c.producto ?? "Sin nombre"}</h3>
        </div>
        <Insignia tono={ESTADO_TONO[c.conjunto]}>{c.estadoRegistro ?? c.conjunto}</Insignia>
      </div>
      <dl className="mt-3">
        <Dato k="Registro sanitario" v={c.registroSanitario} />
        <Dato k="Titular" v={c.titular} />
        <Dato
          k="Principio activo"
          v={c.principiosActivos.map((p) => [p.nombre, [p.cantidad, p.unidad].filter(Boolean).join(" ")].filter(Boolean).join(" ")).join("; ")}
        />
        <Dato k="Forma · vía" v={[c.formaFarmaceutica, c.viaAdministracion].filter(Boolean).join(" · ")} />
        <Dato k="ATC" v={[c.atc, c.descripcionAtc].filter(Boolean).join(" · ")} />
        <Dato k="Vence" v={c.fechaVencimiento ? dia(c.fechaVencimiento) : null} />
        <Dato k="Presentaciones" v={c.presentaciones > 1 ? `${c.presentaciones} en este registro` : c.presentacion} />
      </dl>
    </>
  );
}

function TarjetaPrecio({ c }: { c: CitaPrecio }) {
  return (
    <>
      <p className="etiqueta">{c.id} · CUM {c.cum} · precio máximo regulado</p>
      <h3 className="mt-1 break-words text-[1.05rem]">{c.medicamento ?? c.cum}</h3>
      <dl className="mt-3">
        <Dato k="Institucional" v={plata(c.precioInstitucional)} />
        <Dato k="Comercial" v={plata(c.precioComercial)} />
        <Dato k="Final comercial" v={plata(c.precioFinalComercial)} />
        <Dato k="Circular" v={c.circular} />
        <Dato k="Vigente desde" v={c.vigenciaDesde ? dia(c.vigenciaDesde) : null} />
      </dl>
    </>
  );
}

function TarjetaAgregada({ c }: { c: CitaAgregada }) {
  return (
    <>
      <p className="etiqueta">{c.id} · consulta agregada</p>
      <h3 className="mt-1 text-[1.05rem]">{c.registrosSanitarios} registros sanitarios</h3>
      <dl className="mt-3">
        <Dato k="Presentaciones (CUM)" v={String(c.coincidenciasCum)} />
        <Dato k="Titulares distintos" v={String(c.titularesDistintos)} />
        <Dato k="Filtros" v={Object.entries(c.filtros).map(([k, v]) => `${k}: ${v}`).join(" · ")} />
        {c.porConjunto.map((x) => (
          <Dato key={x.conjunto} k={x.conjunto} v={`${x.registros} registros`} />
        ))}
      </dl>
    </>
  );
}

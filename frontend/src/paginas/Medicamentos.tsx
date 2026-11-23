import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertOctagon, ArrowUpRight, ExternalLink, SearchX, SendHorizontal, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api, post } from "../api/cliente";
import type { CitaAgregada, CitaFicha, CitaMedicamento, CitaPrecio, CitaRegistro, FuenteCargada, RespuestaMedicamentos } from "../api/tipos";
import { AvisoSalud, AvisoUrgencia } from "../componentes/AvisoSalud";
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
    <section aria-labelledby="titulo-med" className="mx-auto flex min-h-[78vh] max-w-5xl flex-col">
      <header className="mb-8">
        <h1 id="titulo-med" className="text-3xl sm:text-4xl">
          Medicamentos
        </h1>
        <p className="mt-3 max-w-2xl text-tinta-2">
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

      <AvisoSalud className="mb-6" />
      <div className="flex-1 space-y-8 pb-6" role="log" aria-live="polite" aria-label="Conversación">
        {vacio && (
          <div className="animate-aparecer">
            <p className="max-w-xl font-display text-2xl font-semibold leading-tight">Pregunta por un medicamento.</p>
            <p className="mt-2 max-w-lg text-tinta-2">
              Responde con la base oficial de INVIMA y, cuando hay una ficha técnica cargada, también efectos, contraindicaciones e
              interacciones con su cita. No indica dosis ni dice qué medicamento tomar: eso lo decide tu médico o farmacéutico.
            </p>
            <ul className="mt-5 max-w-2xl divide-y divide-tinta/12 border-y border-tinta/12">
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
          </div>
        )}

        {conversacion.map((c) => (
          <Respuesta key={c.clave} pregunta={c.pregunta} r={c.respuesta} />
        ))}

        {pendiente && (
          <div className="animate-aparecer space-y-5">
            <Burbuja texto={pendiente} />
            <div className="folio p-5" aria-busy aria-label="Consultando la base de INVIMA">
              <p className="mb-4 text-sm text-tinta-2">Consultando la base de INVIMA…</p>
              <div className="space-y-2.5">
                <Esqueleto className="h-3.5 w-[92%]" />
                <Esqueleto className="h-3.5 w-[74%]" />
                <Esqueleto className="h-3.5 w-[50%]" />
              </div>
            </div>
          </div>
        )}
        {consultar.error && (
          <p role="alert" className="flex items-start gap-2.5 rounded-xl border border-peligro/40 bg-peligro/10 px-4 py-3 text-sm text-peligro">
            <AlertOctagon className="mt-0.5 size-4 shrink-0" aria-hidden />
            {(consultar.error as Error).message}
          </p>
        )}
        <div ref={fin} />
      </div>

      <form onSubmit={enviar} className="folio sticky bottom-4 z-10 p-2.5">
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
      <p className="max-w-[85%] rounded-md bg-folio-2 px-5 py-3 text-[0.97rem] leading-relaxed text-tinta">{texto}</p>
    </div>
  );
}

/** Convierte las referencias [R1], [P1], [E1] del texto en enlaces a su tarjeta (solo si esa cita existe). */
function conReferencias(texto: string, ids: Set<string>) {
  return texto.replace(/\[([RPEF]\d{1,2})\]/g, (m, id) => (ids.has(id) ? `[${id}](#cita-${id})` : m));
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
      <div className="folio p-5 sm:p-6">
        {r.urgencia && <AvisoUrgencia mensaje={r.urgencia.mensaje} />}
        {r.sinEvidencia && !r.limiteClinico && (
          <Insignia tono="aviso" className="mb-3.5">
            <SearchX className="size-3.5" aria-hidden />
            Sin evidencia suficiente
          </Insignia>
        )}
        <div className="space-y-3 text-[0.98rem] leading-relaxed [&_li]:ml-5 [&_li]:list-disc [&_strong]:font-medium [&_strong]:text-tinta">
          <ReactMarkdown
            components={{
              a: ({ href, children }) => {
                const id = (href ?? "").replace("#cita-", "");
                return (
                  <button
                    type="button"
                    onClick={() => irA(id)}
                    className="mx-0.5 inline-grid h-5 min-w-5 -translate-y-0.5 place-items-center rounded-[3px] bg-marca px-1.5 align-middle text-[0.68rem] font-bold text-marca-tx transition-colors hover:bg-accion hover:text-accion-tx"
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
              <li key={a} className="flex gap-2.5 rounded-xl border border-aviso/35 bg-aviso/10 px-3.5 py-2.5 text-sm text-aviso">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span>{a}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-5 border-t border-tinta/10 pt-3.5 text-[0.74rem] leading-relaxed text-tinta-3">{r.aviso}</p>
      </div>

      <FuentesCitadas citas={r.citas} base={base} resaltada={resaltada} />
    </article>
  );
}

const th = "px-3 py-2 text-left text-[0.74rem] font-medium text-tinta-3";
const td = "px-3 py-2.5 align-top";

/** Marcador de la fuente: el mismo amarillo que la referencia [R1] dentro de la respuesta. */
function Marcador({ id }: { id: string }) {
  return <span className="inline-grid h-6 min-w-6 place-items-center rounded-[3px] bg-marca px-1.5 text-[0.72rem] font-bold text-marca-tx">{id}</span>;
}

function EnlaceFuente({ c }: { c: CitaMedicamento }) {
  return (
    <div className="min-w-[7rem] text-[0.72rem] leading-snug text-tinta-3">
      {c.fuente.conjunto}
      {c.fuente.cargadoAt ? <span className="block">cargado el {fecha(c.fuente.cargadoAt)}</span> : null}
      <a
        href={c.fuente.enlace}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-0.5 inline-flex items-center gap-1 text-tinta-2 underline underline-offset-4 hover:text-tinta"
      >
        Ver fuente
        <ExternalLink className="size-3" aria-hidden />
      </a>
    </div>
  );
}

/**
 * Las fuentes citadas, agrupadas por tipo y en tabla: comparar registros o precios lado a lado es lo
 * que hace quien audita. Cada fila lleva su marcador, su estado y su enlace a datos.gov.co.
 */
export function FuentesCitadas({ citas, base, resaltada }: { citas: CitaMedicamento[]; base: string; resaltada: string | null }) {
  const registros = citas.filter((c): c is CitaRegistro => c.tipo === "REGISTRO_INVIMA");
  const precios = citas.filter((c): c is CitaPrecio => c.tipo === "PRECIO_REGULADO");
  const agregadas = citas.filter((c): c is CitaAgregada => c.tipo === "CONSULTA_AGREGADA");
  const fichas = citas.filter((c): c is CitaFicha => c.tipo === "FICHA_TECNICA");
  const fila = (id: string) => cn("border-t border-tinta/10 transition-colors duration-500", resaltada === id && "bg-marca/35");
  return (
    <div className="space-y-4">
      {registros.length > 0 && (
        <section aria-label="Registros sanitarios citados" className="folio overflow-x-auto">
          <table className="w-full min-w-[46rem] border-collapse text-[0.83rem]">
            <caption className="px-3 pb-1 pt-3 text-left text-[0.8rem] font-semibold">Registros sanitarios citados</caption>
            <thead>
              <tr>
                <th className={th} scope="col">Ref.</th>
                <th className={th} scope="col">Producto</th>
                <th className={th} scope="col">Titular · registro</th>
                <th className={th} scope="col">Principio activo</th>
                <th className={th} scope="col">Estado</th>
                <th className={th} scope="col">Vence</th>
                <th className={th} scope="col">Fuente</th>
              </tr>
            </thead>
            <tbody>
              {registros.map((c) => (
                <tr key={c.id} id={`${base}-${c.id}`} className={fila(c.id)}>
                  <th scope="row" className={cn(td, "font-normal")}><Marcador id={c.id} /></th>
                  <td className={td}>
                    <span className="block font-medium">{c.producto ?? "Sin nombre"}</span>
                    <span className="etiqueta block">CUM {c.cum}</span>
                    <span className="block text-[0.76rem] text-tinta-2">
                      {[c.formaFarmaceutica, c.viaAdministracion].filter(Boolean).join(" · ")}
                      {c.presentaciones > 1 ? ` · ${c.presentaciones} presentaciones` : ""}
                    </span>
                  </td>
                  <td className={td}>
                    {c.titular ?? "—"}
                    <span className="num block text-[0.76rem] text-tinta-2">{c.registroSanitario ?? ""}</span>
                  </td>
                  <td className={td}>
                    {c.principiosActivos.length
                      ? c.principiosActivos
                          .map((p) => [p.nombre, [p.cantidad, p.unidad].filter(Boolean).join(" ")].filter(Boolean).join(" "))
                          .join("; ")
                      : "—"}
                    {c.atc ? <span className="etiqueta block">ATC {c.atc}</span> : null}
                  </td>
                  <td className={td}>
                    <Insignia tono={ESTADO_TONO[c.conjunto]}>{c.estadoRegistro ?? c.conjunto}</Insignia>
                  </td>
                  <td className={cn(td, "num whitespace-nowrap")}>{c.fechaVencimiento ? dia(c.fechaVencimiento) : "—"}</td>
                  <td className={td}><EnlaceFuente c={c} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {precios.length > 0 && (
        <section aria-label="Precios máximos regulados citados" className="folio overflow-x-auto">
          <table className="w-full min-w-[40rem] border-collapse text-[0.83rem]">
            <caption className="px-3 pb-1 pt-3 text-left text-[0.8rem] font-semibold">Precio máximo regulado</caption>
            <thead>
              <tr>
                <th className={th} scope="col">Ref.</th>
                <th className={th} scope="col">Medicamento</th>
                <th className={cn(th, "text-right")} scope="col">Institucional</th>
                <th className={cn(th, "text-right")} scope="col">Comercial</th>
                <th className={cn(th, "text-right")} scope="col">Final comercial</th>
                <th className={th} scope="col">Circular · desde</th>
                <th className={th} scope="col">Fuente</th>
              </tr>
            </thead>
            <tbody>
              {precios.map((c) => (
                <tr key={c.id} id={`${base}-${c.id}`} className={fila(c.id)}>
                  <th scope="row" className={cn(td, "font-normal")}><Marcador id={c.id} /></th>
                  <td className={td}>
                    <span className="block font-medium">{c.medicamento ?? c.cum}</span>
                    <span className="etiqueta block">CUM {c.cum}</span>
                  </td>
                  <td className={cn(td, "num text-right")}>{plata(c.precioInstitucional)}</td>
                  <td className={cn(td, "num text-right")}>{plata(c.precioComercial)}</td>
                  <td className={cn(td, "num text-right font-semibold")}>{plata(c.precioFinalComercial)}</td>
                  <td className={td}>
                    {c.circular ?? "—"}
                    <span className="block text-[0.76rem] text-tinta-2">{c.vigenciaDesde ? dia(c.vigenciaDesde) : ""}</span>
                  </td>
                  <td className={td}><EnlaceFuente c={c} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {fichas.map((c) => (
        <section
          key={c.id}
          id={`${base}-${c.id}`}
          aria-label={`Ficha técnica ${c.id}`}
          className={cn("folio p-4 transition-shadow duration-500", resaltada === c.id && "ring-2 ring-marca")}
        >
          <div className="flex flex-wrap items-center gap-3">
            <Marcador id={c.id} />
            <p className="font-display text-[1.05rem] font-semibold">
              {c.titulo} · sección {c.seccion}
            </p>
          </div>
          <p className="etiqueta mt-1">
            Ficha técnica de {c.medicamento ?? "—"} (principio activo: {c.principioActivo ?? "—"}) · registro {c.registro ?? "—"}
          </p>
          <blockquote className="mt-3 max-h-64 overflow-y-auto whitespace-pre-line border-l-2 border-accion/40 pl-3.5 text-[0.88rem] leading-relaxed text-tinta-2">
            {c.extractoLiteral}
          </blockquote>
          {c.extractoTruncado && <p className="mt-1 text-[0.76rem] text-tinta-3">Extracto recortado: la sección completa está en la fuente.</p>}
          <div className="mt-3 border-t border-tinta/10 pt-3"><EnlaceFuente c={c} /></div>
        </section>
      ))}

      {agregadas.map((c) => (
        <section
          key={c.id}
          id={`${base}-${c.id}`}
          aria-label="Consulta agregada"
          className={cn("folio p-4 transition-shadow duration-500", resaltada === c.id && "ring-2 ring-marca")}
        >
          <div className="flex flex-wrap items-center gap-3">
            <Marcador id={c.id} />
            <p className="font-display text-[1.05rem] font-semibold">{c.registrosSanitarios} registros sanitarios</p>
          </div>
          <dl className="mt-3 grid gap-x-8 gap-y-1 text-[0.83rem] sm:grid-cols-2">
            <div className="flex justify-between gap-4"><dt className="text-tinta-3">Presentaciones (CUM)</dt><dd className="num">{c.coincidenciasCum}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-tinta-3">Titulares distintos</dt><dd className="num">{c.titularesDistintos}</dd></div>
            {c.porConjunto.map((x) => (
              <div key={x.conjunto} className="flex justify-between gap-4"><dt className="text-tinta-3">{x.conjunto}</dt><dd className="num">{x.registros} registros</dd></div>
            ))}
          </dl>
          {Object.keys(c.filtros).length > 0 && (
            <p className="etiqueta mt-3">Filtros: {Object.entries(c.filtros).map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
          )}
          <div className="mt-3 border-t border-tinta/10 pt-3"><EnlaceFuente c={c} /></div>
        </section>
      ))}
    </div>
  );
}

const ESTADO_TONO: Record<CitaRegistro["conjunto"], "ok" | "aviso" | "peligro" | "neutro"> = {
  VIGENTE: "ok",
  RENOVACION: "aviso",
  OTROS: "neutro",
  VENCIDO: "peligro",
};

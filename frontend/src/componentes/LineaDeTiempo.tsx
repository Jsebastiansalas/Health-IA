import { useId, useMemo, useState } from "react";
import type { Analito, EventoClinico, RespuestaConsulta, TipoEvento, ValorAnalito } from "../api/tipos";
import { CalendarBlank, ChartLine, ClockCounterClockwise, SearchX, TriangleAlert } from "../iconos";
import { cn } from "../lib/cn";
import { Boton } from "./ui/Boton";
import { Insignia } from "./ui/Insignia";

/** Color de la serie: la familia del verde azulado de la marca, validado para datos en claro y oscuro. */
const SERIE = "#008c99";

const TIPO: Record<TipoEvento, string> = {
  CONSULTA: "Consulta",
  EXAMEN: "Examen",
  HOSPITALIZACION: "Hospitalización",
  PROCEDIMIENTO: "Procedimiento",
  FORMULA: "Fórmula",
  CONTROL: "Control indicado",
  OTRO: "Otro",
};

const fmtFecha = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });
const fmtNumero = (n: number) => n.toLocaleString("es-CO", { maximumFractionDigits: 2 });

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

/**
 * «Mi línea de tiempo»: lo que dicen los documentos ordenado por fecha y la evolución de los exámenes que se
 * repiten. Cada dato lleva su cita. No interpreta: rango y marca son los que trae impresos cada documento.
 */
export function LineaDeTiempo({
  respuesta: r,
  alIrACita,
  alRehacer,
  rehaciendo,
}: {
  respuesta: RespuestaConsulta;
  alIrACita: (n: number) => void;
  alRehacer?: () => void;
  rehaciendo?: boolean;
}) {
  const eventos = r.eventos ?? [];
  const analitos = r.analitos ?? [];

  if (r.sinEvidencia || (eventos.length === 0 && analitos.length === 0)) {
    return (
      <div>
        <Insignia tono="aviso" className="mb-4">
          <SearchX className="size-4" aria-hidden />
          Sin fechas ni resultados en tus documentos
        </Insignia>
        <p className="text-sm leading-relaxed">{r.respuestaAnalitica}</p>
      </div>
    );
  }

  const conEvolucion = analitos.filter((a) => a.comparable && a.valores.filter((v) => v.fecha).length >= 2);
  const sinEvolucion = analitos.filter((a) => !conEvolucion.includes(a));

  return (
    <div className="space-y-8 text-sm leading-relaxed">
      {r.avisoGeneral && <p className="rounded-lg bg-panel-2 px-4 py-3 text-texto-2">{r.avisoGeneral}</p>}

      {eventos.length > 0 && (
        <section aria-labelledby={`ev-${r.consultaId}`}>
          <h3 id={`ev-${r.consultaId}`} className="mb-4 flex items-center gap-2 text-sm font-semibold text-primario-osc">
            <CalendarBlank className="size-4" aria-hidden />
            Lo que pasó, según tus documentos
          </h3>
          <ol className="relative space-y-4 border-l border-borde pl-6">
            {eventos.map((e, i) => (
              <FilaEvento key={`${e.cita}-${i}`} e={e} alIrACita={alIrACita} />
            ))}
          </ol>
        </section>
      )}

      {conEvolucion.length > 0 && (
        <section aria-labelledby={`evo-${r.consultaId}`} className="space-y-6">
          <h3 id={`evo-${r.consultaId}`} className="flex items-center gap-2 text-sm font-semibold text-primario-osc">
            <ChartLine className="size-4" aria-hidden />
            Cómo cambiaron tus resultados
          </h3>
          {conEvolucion.map((a) => (
            <TarjetaAnalito key={a.clave} a={a} alIrACita={alIrACita} grafica />
          ))}
        </section>
      )}

      {sinEvolucion.length > 0 && (
        <section aria-labelledby={`otros-${r.consultaId}`} className="space-y-4">
          <h3 id={`otros-${r.consultaId}`} className="text-sm font-semibold text-primario-osc">
            Otros resultados {conEvolucion.length > 0 && "(una sola medición o sin fecha clara)"}
          </h3>
          {sinEvolucion.map((a) => (
            <TarjetaAnalito key={a.clave} a={a} alIrACita={alIrACita} />
          ))}
        </section>
      )}

      {r.alertas.length > 0 && (
        <ul className="space-y-2">
          {r.alertas.map((t) => (
            <li key={t} className="flex items-start gap-2 text-texto-2">
              <TriangleAlert className="mt-0.5 size-4 shrink-0 text-aviso" aria-hidden />
              {t}
            </li>
          ))}
        </ul>
      )}

      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-borde pt-4 text-xs text-texto-3">
        <span className="flex items-center gap-2">
          <ClockCounterClockwise className="size-4" aria-hidden />
          {r.generadaAt ? `Armada el ${new Date(r.generadaAt).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" })}` : "Armada ahora"}
          {r.guardada && " · tus documentos no cambiaron desde entonces"}
        </span>
        {alRehacer && (
          <Boton variante="fantasma" tamano="sm" onClick={alRehacer} cargando={rehaciendo}>
            Volver a armarla
          </Boton>
        )}
      </footer>
    </div>
  );
}

function FilaEvento({ e, alIrACita }: { e: EventoClinico; alIrACita: (n: number) => void }) {
  return (
    <li className="relative">
      <span className="absolute top-1.5 -left-[29px] size-2.5 rounded-full border-2 border-panel bg-primario" aria-hidden />
      <p className="flex flex-wrap items-center gap-2">
        <span className="num font-medium text-texto">
          {e.fecha ? fmtFecha(e.fecha) : e.referencia ? `${e.fechaTexto} · indicado en el documento del ${fmtFecha(e.referencia)}` : e.fechaTexto}
        </span>
        <Insignia>{TIPO[e.tipo] ?? "Otro"}</Insignia>
      </p>
      <p className="mt-1 text-texto-2">
        {e.texto}
        <Chip n={e.cita} alIr={alIrACita} />
      </p>
      {!e.fecha && !e.referencia && <p className="text-xs text-texto-3">Fecha tal como la escribe el documento.</p>}
    </li>
  );
}

function TarjetaAnalito({ a, alIrACita, grafica = false }: { a: Analito; alIrACita: (n: number) => void; grafica?: boolean }) {
  const unidad = a.unidades.length === 1 ? a.unidades[0] : null;
  return (
    <div className="rounded-xl border border-borde p-4">
      <h4 className="text-base font-semibold text-texto">
        {a.nombre}
        {unidad && <span className="ml-2 text-sm font-normal text-texto-3">{unidad}</span>}
      </h4>
      {grafica && <GraficaEvolucion a={a} alIrACita={alIrACita} />}
      <TablaValores a={a} alIrACita={alIrACita} />
    </div>
  );
}

/** Rango impreso «12,0 - 15,5» o «< 130» → límites numéricos para dibujar la banda (solo si es claro). */
function limitesDeRango(rango: string | null): { min: number | null; max: number | null } | null {
  if (!rango) return null;
  const num = (s: string) => Number(s.replace(/\./g, "").replace(",", "."));
  const entre = rango.match(/(\d+(?:[.,]\d+)?)\s*(?:-|–|a)\s*(\d+(?:[.,]\d+)?)/);
  if (entre) return { min: num(entre[1]!), max: num(entre[2]!) };
  const menor = rango.match(/<\s*=?\s*(\d+(?:[.,]\d+)?)/);
  if (menor) return { min: null, max: num(menor[1]!) };
  const mayor = rango.match(/>\s*=?\s*(\d+(?:[.,]\d+)?)/);
  if (mayor) return { min: num(mayor[1]!), max: null };
  return null;
}

function ticks(min: number, max: number, n = 4): number[] {
  const paso0 = (max - min) / n || 1;
  const pot = 10 ** Math.floor(Math.log10(paso0));
  const paso = [1, 2, 2.5, 5, 10].map((m) => m * pot).find((p) => p >= paso0) ?? paso0;
  const desde = Math.floor(min / paso) * paso;
  const salida: number[] = [];
  for (let v = desde; v <= max + paso * 0.001; v += paso) salida.push(Number(v.toFixed(6)));
  return salida;
}

/**
 * Una serie (un examen) en el tiempo: línea de 2 px, marcadores de 8 px con anillo del color de la superficie,
 * banda gris con el rango impreso (si todos los documentos traen el mismo), valor rotulado solo en el último
 * punto y tooltip al pasar o enfocar. La tabla de abajo trae todos los valores con su cita.
 */
function GraficaEvolucion({ a, alIrACita }: { a: Analito; alIrACita: (n: number) => void }) {
  const id = useId();
  const [activo, setActivo] = useState<number | null>(null);
  const puntos = useMemo(() => a.valores.filter((v): v is ValorAnalito & { fecha: string } => !!v.fecha), [a.valores]);
  const rangos = new Set(puntos.map((p) => p.rango ?? ""));
  const banda = rangos.size === 1 ? limitesDeRango(puntos[0]?.rango ?? null) : null;

  const W = 560,
    H = 190,
    izq = 44,
    der = 56,
    arr = 14,
    abj = 30;
  const tiempos = puntos.map((p) => new Date(`${p.fecha}T12:00:00`).getTime());
  const t0 = Math.min(...tiempos),
    t1 = Math.max(...tiempos);
  const valores = puntos.map((p) => p.valor).concat(banda ? [banda.min, banda.max].filter((x): x is number => x !== null) : []);
  let vMin = Math.min(...valores),
    vMax = Math.max(...valores);
  const holgura = (vMax - vMin || Math.abs(vMax) || 1) * 0.15;
  vMin -= holgura;
  vMax += holgura;
  const marcas = ticks(vMin, vMax);
  vMin = Math.min(vMin, marcas[0]!);
  vMax = Math.max(vMax, marcas[marcas.length - 1]!);
  const x = (t: number) => izq + (t1 === t0 ? (W - izq - der) / 2 : ((t - t0) / (t1 - t0)) * (W - izq - der));
  const y = (v: number) => arr + (1 - (v - vMin) / (vMax - vMin)) * (H - arr - abj);
  const ruta = puntos.map((p, i) => `${i ? "L" : "M"}${x(tiempos[i]!).toFixed(1)},${y(p.valor).toFixed(1)}`).join(" ");
  const ultimo = puntos.length - 1;
  const p = activo !== null ? puntos[activo] : null;

  return (
    <figure className="relative mt-3" aria-labelledby={`${id}-t`}>
      <figcaption id={`${id}-t`} className="sr-only">
        Evolución de {a.nombre}: {puntos.map((q) => `${fmtFecha(q.fecha)} ${q.valorTexto}`).join("; ")}.
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full overflow-visible" aria-hidden={puntos.length === 0}>
        {banda && (
          <rect
            x={izq}
            width={W - izq - der}
            y={y(banda.max ?? vMax)}
            height={y(banda.min ?? vMin) - y(banda.max ?? vMax)}
            className="fill-texto/[0.07]"
          />
        )}
        {marcas.map((m) => (
          <g key={m}>
            <line x1={izq} x2={W - der} y1={y(m)} y2={y(m)} className="stroke-borde" strokeWidth={1} />
            <text x={izq - 8} y={y(m)} dy="0.32em" textAnchor="end" className="fill-texto-3 text-[11px] tabular-nums">
              {fmtNumero(m)}
            </text>
          </g>
        ))}
        {puntos.map((q, i) => (
          <text
            key={`x-${i}`}
            x={x(tiempos[i]!)}
            y={H - 8}
            textAnchor={puntos.length > 1 && i === 0 ? "start" : puntos.length > 1 && i === ultimo ? "end" : "middle"}
            className={cn("fill-texto-3 text-[11px]", puntos.length > 4 && i !== 0 && i !== ultimo && "hidden sm:inline")}
          >
            {fmtFecha(q.fecha)}
          </text>
        ))}
        <path d={ruta} fill="none" stroke={SERIE} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {puntos.map((q, i) => (
          <g
            key={`p-${i}`}
            role="button"
            tabIndex={0}
            aria-label={`${fmtFecha(q.fecha)}: ${q.valorTexto}${q.unidad ? ` ${q.unidad}` : ""}. Abrir la cita ${q.cita}`}
            className="cursor-pointer outline-none [&:focus-visible>circle:last-child]:stroke-texto"
            onMouseEnter={() => setActivo(i)}
            onMouseLeave={() => setActivo(null)}
            onFocus={() => setActivo(i)}
            onBlur={() => setActivo(null)}
            onClick={() => alIrACita(q.cita)}
            onKeyDown={(ev) => {
              if (ev.key === "Enter" || ev.key === " ") {
                ev.preventDefault();
                alIrACita(q.cita);
              }
            }}
          >
            <circle cx={x(tiempos[i]!)} cy={y(q.valor)} r={14} fill="transparent" />
            <circle cx={x(tiempos[i]!)} cy={y(q.valor)} r={activo === i ? 6 : 4.5} fill={SERIE} className="stroke-panel" strokeWidth={2} />
          </g>
        ))}
        {ultimo >= 0 && (
          <text x={x(tiempos[ultimo]!) + 10} y={y(puntos[ultimo]!.valor)} dy="0.32em" className="fill-texto text-[12px] font-semibold tabular-nums">
            {puntos[ultimo]!.valorTexto}
          </text>
        )}
      </svg>
      {banda && <p className="mt-1 text-xs text-texto-3">Banda gris: rango impreso en el documento ({puntos[0]?.rango}).</p>}
      {p && activo !== null && (
        <div
          role="status"
          className="panel pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full px-3 py-2 text-xs shadow-lg"
          style={{ left: `${(x(tiempos[activo]!) / W) * 100}%`, top: `${(y(p.valor) / H) * 100}%`, marginTop: -12 }}
        >
          <p className="font-medium text-texto">{fmtFecha(p.fecha)}</p>
          <p className="num text-texto">
            {p.valorTexto} {p.unidad}
          </p>
          {p.rango && <p className="text-texto-3">Rango impreso: {p.rango}</p>}
          {p.marca && <p className="text-texto-3">Marca impresa: {p.marca}</p>}
          <p className="text-texto-3">Clic para ver la cita {p.cita}</p>
        </div>
      )}
    </figure>
  );
}

function TablaValores({ a, alIrACita }: { a: Analito; alIrACita: (n: number) => void }) {
  return (
    <table className="mt-3 w-full text-left text-sm">
      <caption className="sr-only">Valores de {a.nombre} con su cita</caption>
      <thead className="text-xs text-texto-3">
        <tr>
          <th scope="col" className="py-1 pr-3 font-medium">
            Fecha
          </th>
          <th scope="col" className="py-1 pr-3 font-medium">
            Valor
          </th>
          <th scope="col" className="hidden py-1 pr-3 font-medium sm:table-cell">
            Rango impreso
          </th>
          <th scope="col" className="py-1 font-medium">
            Fuente
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-borde">
        {a.valores.map((v, i) => (
          <tr key={`${v.cita}-${i}`}>
            <td className="py-2 pr-3 text-texto-2">{v.fecha ? fmtFecha(v.fecha) : (v.fechaTexto ?? "Sin fecha")}</td>
            <td className="num py-2 pr-3 text-texto">
              {v.valorTexto} {v.unidad}
              {v.marca && (
                <Insignia className="ml-2" title="Marca impresa en el documento">
                  {v.marca}
                </Insignia>
              )}
            </td>
            <td className="hidden py-2 pr-3 text-texto-2 sm:table-cell">{v.rango ?? "—"}</td>
            <td className="py-2">
              <Chip n={v.cita} alIr={alIrACita} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

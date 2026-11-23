import { Pill, SearchX, TriangleAlert } from "lucide-react";
import type { RespuestaConsulta } from "../api/tipos";
import { FuentesCitadas } from "../paginas/Medicamentos";
import { Insignia } from "./ui/Insignia";

function Chip({ n, alIr }: { n: number; alIr: (n: number) => void }) {
  return (
    <button
      type="button"
      onClick={() => alIr(n)}
      className="mx-0.5 inline-grid size-5 -translate-y-0.5 place-items-center rounded-md bg-marca align-middle text-[0.7rem] font-bold text-marca-tx transition-colors hover:bg-accion hover:text-accion-tx"
      aria-label={`Ir a la cita ${n}`}
    >
      {n}
    </button>
  );
}

/**
 * «Advertencias de mis medicamentos»: lo que escriben los documentos y lo que advierte la ficha técnica
 * frente a ello. Cada advertencia lleva una cita al documento y otra a la ficha. No elige, recomienda ni dosifica.
 */
export function CruceMedicamentos({
  respuesta: r,
  alIrACita,
}: {
  respuesta: RespuestaConsulta;
  alIrACita: (n: number) => void;
}) {
  const medicamentos = r.medicamentos ?? [];
  const advertencias = r.advertencias ?? [];
  const fichas = r.fichas ?? [];
  const sinFicha = r.sinFicha ?? [];

  if (r.sinEvidencia || medicamentos.length === 0) {
    return (
      <div>
        <Insignia tono="aviso" className="mb-3.5">
          <SearchX className="size-3.5" aria-hidden />
          Sin medicamentos en tus documentos
        </Insignia>
        <p className="text-[0.98rem] leading-relaxed">{r.respuestaAnalitica}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 text-[0.98rem] leading-relaxed">
      <section aria-labelledby={`meds-${r.consultaId}`}>
        <h3 id={`meds-${r.consultaId}`} className="mb-1.5 flex items-center gap-2 text-sm font-semibold text-accion">
          <Pill className="size-4" aria-hidden />
          Medicamentos que aparecen en tus documentos
        </h3>
        <ul className="space-y-1">
          {medicamentos.map((m) => (
            <li key={`${m.nombre}-${m.cita}`} className="ml-5 list-disc">
              {m.nombre}
              <Chip n={m.cita} alIr={alIrACita} />
              {m.ficha === false && <span className="ml-2 text-[0.8rem] text-tinta-3">(sin ficha técnica cargada)</span>}
            </li>
          ))}
        </ul>
        {((r.diagnosticos ?? []).length > 0 || (r.alergias ?? []).length > 0) && (
          <p className="mt-2 text-[0.88rem] text-tinta-2">
            Datos de tus documentos con los que se compararon:{" "}
            {[...(r.diagnosticos ?? []).map((d) => ({ ...d, t: "diagnóstico" })), ...(r.alergias ?? []).map((a) => ({ ...a, t: "alergia" }))].map(
              (d, i) => (
                <span key={`${d.texto}-${i}`}>
                  {i > 0 && "; "}
                  {d.texto} ({d.t}) <Chip n={d.cita} alIr={alIrACita} />
                </span>
              ),
            )}
          </p>
        )}
      </section>

      <section aria-labelledby={`adv-${r.consultaId}`}>
        <h3 id={`adv-${r.consultaId}`} className="mb-1.5 text-sm font-semibold text-accion">
          Lo que advierten las fichas frente a lo que dicen tus documentos
        </h3>
        {advertencias.length === 0 ? (
          <p className="text-tinta-2">
            No encontré advertencias de las fichas cargadas que se relacionen con lo que escriben tus documentos. Eso no significa que no
            existan: revisa el prospecto y pregunta a tu médico o farmacéutico.
          </p>
        ) : (
          <ul className="space-y-3">
            {advertencias.map((a, i) => (
              <li key={i} className="rounded-md border border-tinta/12 bg-folio-2 p-3.5">
                <p className="text-[0.82rem] font-semibold text-tinta-2">
                  {a.medicamento} <Chip n={a.citaMedicamento} alIr={alIrACita} /> ↔ {a.dato} <Chip n={a.citaDato} alIr={alIrACita} />
                </p>
                <p className="mt-1">
                  {a.texto} <span className="text-[0.8rem] text-tinta-3">(ficha {a.ficha})</span>
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {sinFicha.length > 0 && (
        <p className="text-[0.88rem] text-tinta-2">
          Sin ficha técnica cargada: {sinFicha.join(", ")}. Consulta su prospecto o pregunta a tu farmacéutico.
        </p>
      )}

      {fichas.length > 0 && (
        <section aria-label="Fichas técnicas citadas">
          <FuentesCitadas citas={fichas} base={`cita-${r.consultaId}`} resaltada={null} />
        </section>
      )}

      {r.avisoGeneral && (
        <p className="flex items-start gap-2 text-[0.8rem] leading-relaxed text-tinta-3">
          <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {r.avisoGeneral}
        </p>
      )}
    </div>
  );
}

import { BotonLeer } from "./BotonLeer";
import { BookOpen, MessageCircleQuestion, SearchX, TriangleAlert } from "../iconos";
import type { RespuestaConsulta } from "../api/tipos";
import { AvisoUrgencia } from "./AvisoSalud";
import { Insignia } from "./ui/Insignia";

/**
 * «Explícame este documento», en dos capas que no se mezclan: lo que DICE el documento (cada punto con su
 * cita literal) y qué SIGNIFICAN sus términos (explicación general, rotulada, que no habla del caso).
 */
export function ExplicacionDocumento({
  respuesta: r,
  alIrACita,
}: {
  respuesta: RespuestaConsulta;
  alIrACita: (n: number) => void;
}) {
  const hallazgos = r.hallazgos ?? [];
  const terminos = r.terminos ?? [];
  const senales = r.senalesDeAlarma ?? [];
  const preguntas = r.preguntasParaElMedico ?? [];

  if (r.sinEvidencia) {
    return (
      <div>
        <Insignia tono="aviso" className="mb-4">
          <SearchX className="size-4" aria-hidden />
          Sin evidencia suficiente
        </Insignia>
        <p className="text-sm leading-relaxed">
          {r.deQueTrata || "No pude explicar este documento con lo que dice su texto. Prueba con una foto más nítida o con el PDF."}
        </p>
      </div>
    );
  }

  // Lo mismo que se ve, en el mismo orden.
  const paraEscuchar = [
    r.deQueTrata,
    senales.length ? `El documento marca como importante: ${senales.join("; ")}.` : "",
    ...hallazgos.map((h) => h.texto),
    preguntas.length ? `Preguntas para tu médico. ${preguntas.join(" ")}` : "",
    r.avisoGeneral,
  ]
    .filter(Boolean)
    .join("\n");

  return (
    <div className="space-y-6 text-sm leading-relaxed">
      <BotonLeer texto={paraEscuchar} />
      {r.deQueTrata && (
        <section aria-labelledby={`trata-${r.consultaId}`}>
          <h3 id={`trata-${r.consultaId}`} className="mb-2 text-sm font-semibold text-primario">
            De qué trata
          </h3>
          <p>{r.deQueTrata}</p>
        </section>
      )}

      {senales.length > 0 && (
        <section aria-label="Señales de alarma que marca el documento">
          <AvisoUrgencia
            mensaje={`El documento marca como importante: ${senales.join("; ")}. Si tienes síntomas o dudas, consulta a tu médico; en una urgencia llama al 123.`}
          />
        </section>
      )}

      {hallazgos.length > 0 && (
        <section aria-labelledby={`dice-${r.consultaId}`}>
          <h3 id={`dice-${r.consultaId}`} className="mb-2 text-sm font-semibold text-primario">
            Lo que dice el documento
          </h3>
          <ul className="space-y-2">
            {hallazgos.map((h, i) => (
              <li key={i} className="ml-4 list-disc">
                {h.texto}
                {h.cita != null && (
                  <button
                    type="button"
                    onClick={() => alIrACita(h.cita!)}
                    className="mx-1 inline-grid size-5 -translate-y-0.5 place-items-center rounded-lg bg-cita align-middle text-xs font-semibold text-cita-tx transition-colors hover:bg-primario hover:text-primario-tx"
                    aria-label={`Ir a la cita ${h.cita}`}
                  >
                    {h.cita}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {terminos.length > 0 && (
        <section aria-labelledby={`terminos-${r.consultaId}`} className="rounded-lg border border-borde bg-panel-2 p-4">
          <h3 id={`terminos-${r.consultaId}`} className="flex items-center gap-2 text-sm font-semibold">
            <BookOpen className="size-4 text-primario" aria-hidden />
            Qué significan estos términos
          </h3>
          <p className="mb-3 mt-0.5 text-xs text-texto-3">
            Explicación general de las palabras; no es un diagnóstico ni habla de tu caso.
          </p>
          {r.glosario && !r.glosario.revisado && (
            <p className="mb-3 text-xs text-texto-3">Glosario de MedTender: {r.glosario.revision.toLowerCase()}.</p>
          )}
          <dl className="space-y-3">
            {terminos.map((t) => (
              <div key={t.termino}>
                <dt className="font-semibold">{t.termino}</dt>
                <dd className="text-texto-2">{t.explicacion}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {preguntas.length > 0 && (
        <section aria-labelledby={`preguntas-${r.consultaId}`}>
          <h3 id={`preguntas-${r.consultaId}`} className="mb-2 flex items-center gap-2 text-sm font-semibold text-primario">
            <MessageCircleQuestion className="size-4" aria-hidden />
            Preguntas para llevarle a tu médico
          </h3>
          <ul className="space-y-2">
            {preguntas.map((p) => (
              <li key={p} className="ml-4 list-disc">
                {p}
              </li>
            ))}
          </ul>
        </section>
      )}

      {r.avisoGeneral && (
        <p className="flex items-start gap-2 text-xs leading-relaxed text-texto-3">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          {r.avisoGeneral}
        </p>
      )}
    </div>
  );
}

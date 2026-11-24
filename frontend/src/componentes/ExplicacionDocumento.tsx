import { BookOpen, MessageCircleQuestion, SearchX, TriangleAlert } from "lucide-react";
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
        <Insignia tono="aviso" className="mb-3.5">
          <SearchX className="size-3.5" aria-hidden />
          Sin evidencia suficiente
        </Insignia>
        <p className="text-[0.98rem] leading-relaxed">
          {r.deQueTrata || "No pude explicar este documento con lo que dice su texto. Prueba con una foto más nítida o con el PDF."}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 text-[0.98rem] leading-relaxed">
      {r.deQueTrata && (
        <section aria-labelledby={`trata-${r.consultaId}`}>
          <h3 id={`trata-${r.consultaId}`} className="mb-1.5 text-sm font-semibold text-accion">
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
          <h3 id={`dice-${r.consultaId}`} className="mb-1.5 text-sm font-semibold text-accion">
            Lo que dice el documento
          </h3>
          <ul className="space-y-2">
            {hallazgos.map((h, i) => (
              <li key={i} className="ml-5 list-disc">
                {h.texto}
                {h.cita != null && (
                  <button
                    type="button"
                    onClick={() => alIrACita(h.cita!)}
                    className="mx-1 inline-grid size-5 -translate-y-0.5 place-items-center rounded-md bg-marca align-middle text-[0.7rem] font-bold text-marca-tx transition-colors hover:bg-accion hover:text-accion-tx"
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
        <section aria-labelledby={`terminos-${r.consultaId}`} className="rounded-md border border-tinta/12 bg-folio-2 p-4">
          <h3 id={`terminos-${r.consultaId}`} className="flex items-center gap-2 text-sm font-semibold">
            <BookOpen className="size-4 text-accion" aria-hidden />
            Qué significan estos términos
          </h3>
          <p className="mb-3 mt-0.5 text-[0.8rem] text-tinta-3">
            Explicación general de las palabras; no es un diagnóstico ni habla de tu caso.
          </p>
          {r.glosario && !r.glosario.revisado && (
            <p className="mb-3 text-[0.76rem] text-tinta-3">Glosario de MedTender: {r.glosario.revision.toLowerCase()}.</p>
          )}
          <dl className="space-y-2.5">
            {terminos.map((t) => (
              <div key={t.termino}>
                <dt className="font-semibold">{t.termino}</dt>
                <dd className="text-tinta-2">{t.explicacion}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {preguntas.length > 0 && (
        <section aria-labelledby={`preguntas-${r.consultaId}`}>
          <h3 id={`preguntas-${r.consultaId}`} className="mb-1.5 flex items-center gap-2 text-sm font-semibold text-accion">
            <MessageCircleQuestion className="size-4" aria-hidden />
            Preguntas para llevarle a tu médico
          </h3>
          <ul className="space-y-1.5">
            {preguntas.map((p) => (
              <li key={p} className="ml-5 list-disc">
                {p}
              </li>
            ))}
          </ul>
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

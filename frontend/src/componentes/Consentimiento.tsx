import { ShieldCheck } from "../iconos";
import { CONTACTO_PRIVACIDAD, RESPONSABLE } from "../lib/legal";
import { Boton } from "./ui/Boton";

/** Lo que la persona acepta antes de usar sus documentos de salud. El texto cambia con la versión del servidor. */
const PUNTOS = [
  "MedTender está en pruebas cerradas: puede equivocarse. Compara siempre con tu médico o tu farmacéutico antes de decidir algo sobre tu salud.",
  "Subirás documentos médicos (historias clínicas, resultados, órdenes, prospectos). Son datos sensibles. Si subes documentos de otra persona, declaras que tienes derecho a hacerlo o su autorización. Si eres menor de edad, usa esta cuenta con un adulto responsable.",
  "Para leerlos y responderte usamos un servicio de inteligencia artificial de un tercero: Google Gemini, que puede procesar la información fuera de Colombia. En esta etapa usamos su versión gratuita, y Google puede conservar y usar lo que se le envía para mejorar sus productos. Por eso sube solo lo que necesites.",
  "Antes de enviarle el texto ocultamos nombres, cédulas, teléfonos, correos y direcciones cuando aparecen con una etiqueta (por ejemplo «Paciente:» o «CC»). Este ocultamiento no es perfecto: un nombre suelto dentro de una frase puede no detectarse.",
  "El archivo original se elimina del servidor después de leerlo. Guardamos fragmentos de texto tal como aparecen en el documento (con tus datos) y tus preguntas, para poder responderte y citar el texto exacto.",
  "Puedes borrar tu historial de preguntas y eliminar tu cuenta con todo su contenido cuando quieras. Las copias de seguridad conservan los datos hasta 14 días más. El registro de accesos (tu correo, la fecha y tu dirección IP, nunca el contenido de tus documentos ni de tus preguntas) se conserva sin fecha de vencimiento.",
  "MedTender explica y cita lo que dicen tus documentos. No es un médico, no diagnostica, no receta ni indica dosis. Si es una urgencia, llama al 123.",
];

export function Consentimiento({ version, aceptando, error, alAceptar }: { version: string; aceptando: boolean; error?: string; alAceptar: () => void }) {
  return (
    <section aria-labelledby="titulo-consentimiento" className="panel mb-8 border-l-0 p-6 sm:p-8">
      <h2 id="titulo-consentimiento" className="flex items-center gap-3 text-xl">
        <ShieldCheck className="size-6 text-primario" aria-hidden />
        Antes de usar tus documentos de salud
      </h2>
      <p className="mt-2 text-texto-2">Lee esto con calma. Necesitamos tu aceptación para continuar.</p>
      <ul className="mt-4 max-w-3xl space-y-3 text-sm leading-relaxed">
        {PUNTOS.map((p) => (
          <li key={p} className="flex gap-3">
            <span className="mt-2 size-2 shrink-0 rounded-full bg-texto-3" aria-hidden />
            <span>{p}</span>
          </li>
        ))}
      </ul>
      {(RESPONSABLE || CONTACTO_PRIVACIDAD) && (
        <p className="mt-4 max-w-3xl text-sm leading-relaxed text-texto-2">
          Responsable del tratamiento: {RESPONSABLE || "titular del proyecto MedTender"}
          {CONTACTO_PRIVACIDAD ? ` · contacto: ${CONTACTO_PRIVACIDAD}` : ""}.
        </p>
      )}
      {error && (
        <p role="alert" className="mt-4 text-sm text-peligro">
          {error}
        </p>
      )}
      <div className="mt-6 flex flex-wrap items-center gap-4">
        <Boton variante="primario" onClick={alAceptar} cargando={aceptando}>
          Entiendo y acepto
        </Boton>
        <span className="etiqueta">Versión {version}</span>
      </div>
    </section>
  );
}

import { ShieldCheck } from "lucide-react";
import { Boton } from "./ui/Boton";

/** Lo que la persona acepta antes de usar sus documentos de salud. El texto cambia con la versión del servidor. */
const PUNTOS = [
  "Subirás documentos médicos (historias clínicas, resultados, órdenes). Son datos sensibles.",
  "Para leerlos y responderte usamos un servicio de inteligencia artificial de un proveedor externo (Google Gemini): el texto de tus documentos y tus preguntas se le envían. Por ahora no ocultamos automáticamente tus datos personales antes de enviarlos.",
  "El archivo original se elimina del servidor después de leerlo. Guardamos fragmentos de texto y tus preguntas para poder responderte.",
  "Puedes borrar tu historial de preguntas y eliminar tu cuenta con todo su contenido cuando quieras.",
  "MedTender explica y cita lo que dicen tus documentos. No es un médico, no diagnostica ni receta. Si es una urgencia, llama al 123.",
];

export function Consentimiento({ version, aceptando, error, alAceptar }: { version: string; aceptando: boolean; error?: string; alAceptar: () => void }) {
  return (
    <section aria-labelledby="titulo-consentimiento" className="folio mb-7 border-l-0 p-6 sm:p-8">
      <h2 id="titulo-consentimiento" className="flex items-center gap-2.5 text-[1.4rem]">
        <ShieldCheck className="size-6 text-accion" aria-hidden />
        Antes de usar tus documentos de salud
      </h2>
      <p className="mt-2 text-tinta-2">Lee esto con calma. Necesitamos tu aceptación para continuar.</p>
      <ul className="mt-5 max-w-3xl space-y-3 text-[0.95rem] leading-relaxed">
        {PUNTOS.map((p) => (
          <li key={p} className="flex gap-3">
            <span className="mt-2 size-1.5 shrink-0 rounded-full bg-tinta-3" aria-hidden />
            <span>{p}</span>
          </li>
        ))}
      </ul>
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

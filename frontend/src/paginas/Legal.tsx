import { Link } from "react-router-dom";
import { ArrowLeft } from "../iconos";
import { Marca } from "../componentes/Marca";
import { boton } from "../componentes/ui/Boton";
import { CONTACTO_PRIVACIDAD } from "../lib/legal";
import { resumenIa, useProveedorIa } from "../lib/proveedorIa";

function Hoja({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-fondo">
      <header className="border-b border-borde bg-panel">
        <div className="mx-auto flex h-12 max-w-3xl items-center justify-between px-6">
          <Link to="/" aria-label="MedTender, inicio">
            <Marca />
          </Link>
          <Link to="/" className={boton({ variante: "fantasma", tamano: "sm" })}>
            <ArrowLeft className="size-4" aria-hidden />
            Volver
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-6 py-12">
        <h1 className="text-4xl font-semibold leading-10">{titulo}</h1>
        <p className="mt-4 rounded-xl border border-aviso/40 bg-aviso/10 px-4 py-3 text-sm text-aviso" role="note">
          Borrador. Este texto resume cómo funciona MedTender hoy y está pendiente de revisión legal; todavía no es la política definitiva.
        </p>
        <div className="mt-8 space-y-8 text-base text-texto-2 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-texto [&_li]:ml-5 [&_li]:list-disc [&_ul]:mt-2 [&_ul]:space-y-2">
          {children}
        </div>
        {CONTACTO_PRIVACIDAD && (
          <p className="mt-10 text-sm text-texto-3">
            Contacto sobre datos personales:{" "}
            <a className="underline underline-offset-4" href={`mailto:${CONTACTO_PRIVACIDAD}`}>
              {CONTACTO_PRIVACIDAD}
            </a>
          </p>
        )}
      </main>
    </div>
  );
}

export function PaginaPrivacidad() {
  const ia = useProveedorIa();
  return (
    <Hoja titulo="Privacidad">
      <section>
        <h2>Qué datos tratamos</h2>
        <ul>
          <li>Tu cuenta: nombre, correo y una huella de tu contraseña (nunca la contraseña).</li>
          <li>El texto de los documentos que subes, dividido en fragmentos, para poder responder y citar el texto exacto.</li>
          <li>Las fechas, consultas y resultados de laboratorio que la inteligencia artificial encuentra en cada documento, para armar tu
            línea de tiempo. Se guardan cifrados y se borran con el documento.</li>
          <li>Tus preguntas y las respuestas.</li>
          <li>Si compartes un expediente con un cuidador: su correo, qué le permites y cuándo entró. Esa persona ve los documentos
            de ese expediente hasta que le quites el acceso.</li>
          <li>Un registro de accesos con tu correo, la fecha y tu dirección IP, nunca el contenido de tus documentos ni de tus preguntas.</li>
        </ul>
      </section>
      <section>
        <h2>Adónde van</h2>
        <p>
          {resumenIa(ia)} Antes de enviar el texto ocultamos nombres, cédulas, teléfonos, correos y direcciones cuando aparecen con una
          etiqueta. Ese ocultamiento no es perfecto.
        </p>
      </section>
      <section>
        <h2>Cuánto tiempo se conservan</h2>
        <ul>
          <li>El archivo original se elimina del servidor después de leerlo.</li>
          <li>Los fragmentos de texto y tus preguntas se conservan hasta que los borres o elimines tu cuenta. En «Mis datos» puedes
            hacer que tus preguntas y respuestas se borren solas pasado un plazo y descargar una copia de lo que hay sobre ti.</li>
          <li>Las copias de seguridad conservan los datos hasta 14 días más después de borrarlos.</li>
          <li>El registro de accesos se conserva sin fecha de vencimiento.</li>
        </ul>
      </section>
      <section>
        <h2>Tus decisiones</h2>
        <p>Puedes borrar el historial de preguntas de un expediente y eliminar tu cuenta con todo su contenido desde el menú de tu usuario.</p>
      </section>
    </Hoja>
  );
}

export function PaginaTerminos() {
  return (
    <Hoja titulo="Términos de uso">
      <section>
        <h2>Qué es MedTender</h2>
        <p>
          Una herramienta de apoyo que explica y cita lo que dicen tus documentos. No es un médico, no diagnostica, no receta y no indica dosis. No
          sustituye a un profesional de la salud. En una urgencia, llama al 123.
        </p>
      </section>
      <section>
        <h2>Pruebas cerradas</h2>
        <p>MedTender está en pruebas con personas invitadas y puede equivocarse. Compara siempre con tu médico o tu farmacéutico.</p>
      </section>
      <section>
        <h2>Tus documentos</h2>
        <ul>
          <li>Sube solo documentos tuyos o de personas que te hayan autorizado.</li>
          <li>Si eres menor de edad, usa tu cuenta con un adulto responsable.</li>
          <li>No subas más datos de los necesarios.</li>
        </ul>
      </section>
    </Hoja>
  );
}

export function PaginaNoEncontrada() {
  return (
    <div className="grid min-h-screen place-items-center bg-fondo px-6">
      <div className="max-w-md text-center">
        <Marca className="justify-center" />
        <p className="mt-10 text-sm font-medium text-texto-3">Error 404</p>
        <h1 className="mt-2 text-3xl font-semibold">No encontramos esa página</h1>
        <p className="mt-3 text-base text-texto-2">La dirección no existe o ya no está disponible. Puedes volver al inicio y seguir desde ahí.</p>
        <Link to="/" className={boton({ variante: "primario", tamano: "md" }) + " mt-8"}>
          Volver al inicio
        </Link>
      </div>
    </div>
  );
}

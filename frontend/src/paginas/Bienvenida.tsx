import { Landing, type ContenidoLanding } from "./Landing";

const ORGANIZACIONES: ContenidoLanding = {
  titular: "Respuestas sobre tus expedientes de salud, con la fuente a la vista.",
  subtitular:
    "MedTender lee licitaciones médicas, historias clínicas y auditorías, y responde con el documento, la página y el texto exacto. Cuando los documentos no lo respaldan, lo dice.",
  cta: { texto: "Ingresar a mi organización", a: "/ingreso" },
  apoyo: "Cada respuesta se puede verificar abriendo el original desde tu propio equipo.",
  pregunta: "¿Qué debe acreditar el oferente del monitor multiparamétrico?",
  respuesta: "Debe acreditar registro sanitario INVIMA vigente y el certificado de calibración del equipo ofertado.",
  fuente: { documento: "Ficha técnica, página 6", extracto: "El oferente deberá acreditar registro sanitario INVIMA vigente y certificado de calibración del equipo ofertado." },
  lema: "Una respuesta sin fuente no es una respuesta. MedTender solo contesta con lo que dice tu documento, y cuando no alcanza, te lo dice.",
  pasos: [
    { titulo: "Sube el expediente", texto: "Pliegos, adendas, fichas técnicas e historias clínicas en PDF o en foto. Se leen, se indexan y el original se elimina del servidor." },
    { titulo: "Pregunta como lo harías a un colega", texto: "Escribe la duda en tus palabras. Las adendas pesan más que el pliego base y se señalan como alerta." },
    { titulo: "Verifica la fuente", texto: "Cada punto trae documento, página, texto literal y huella. Abre el original desde tu carpeta y compara." },
  ],
  beneficios: [
    { titulo: "Citas que se pueden comprobar", texto: "El extracto es literal y se verifica contra el texto real; no se parafrasea la evidencia." },
    { titulo: "Se abstiene cuando no hay evidencia", texto: "Si los documentos no respaldan la respuesta, MedTender lo dice en lugar de adivinar." },
    { titulo: "Cada organización ve solo lo suyo", texto: "Los expedientes se aíslan por organización y por permisos de lectura, edición y administración." },
    { titulo: "Medicamentos con datos abiertos", texto: "Consulta registros sanitarios, vigencias y precios regulados con los datos abiertos de INVIMA." },
  ],
  preguntas: [
    { p: "¿Dónde se guardan mis documentos?", r: "El archivo original se elimina del servidor después de leerlo y queda un acta de purga con su huella. Guardamos fragmentos de texto para poder responder y citar." },
    { p: "¿Qué pasa si el documento no responde mi pregunta?", r: "MedTender se abstiene y lo dice de forma explícita. No completa con conocimiento propio." },
    { p: "¿Da dosis, diagnósticos o recomendaciones?", r: "No. Explica y cita lo que dicen los documentos. Si alguien pide una dosis o un diagnóstico, remite a su médico o farmacéutico." },
    { p: "¿Puedo abrir el documento original?", r: "Sí, desde tu propio equipo. El visor compara la huella SHA 256 del archivo con la registrada. El archivo nunca se sube." },
    { p: "¿Usa inteligencia artificial de terceros?", r: "Sí, Google Gemini. Antes de enviarle el texto se ocultan nombres, cédulas, teléfonos y correos cuando aparecen con una etiqueta. En esta etapa se usa su versión gratuita." },
    { p: "¿Quién puede usarlo hoy?", r: "MedTender está en pruebas cerradas con personas invitadas. Si tu organización quiere probarlo, escríbenos." },
  ],
  riesgo: {
    titulo: "El original no se queda en el servidor",
    texto: "Se elimina después de indexarlo, con verificación y un acta de purga. Puedes comprobar la fuente siempre desde tu propio equipo.",
  },
  cierre: "Tu próxima licitación o auditoría, con la fuente a un clic.",
  alterna: { texto: "Para personas", a: "/personas" },
};

const PERSONAS: ContenidoLanding = {
  titular: "Entiende los documentos que te entregan en el hospital.",
  subtitular:
    "Sube tu resultado, tu orden o tu historia clínica y MedTender te lo explica en palabras sencillas, con el texto exacto al lado. No diagnostica ni receta.",
  cta: { texto: "Crear mi cuenta", a: "/registro" },
  apoyo: "Tu archivo original se elimina del servidor después de leerlo, y puedes borrar tu cuenta cuando quieras.",
  pregunta: "¿Qué dice mi examen sobre el colesterol?",
  respuesta: "El informe registra un colesterol LDL de 160 mg/dL y lo marca como alto.",
  fuente: { documento: "Resultado de laboratorio, página 1", extracto: "Colesterol LDL 160 mg/dL (ref < 130) ALTO" },
  lema: "Los papeles del hospital deberían poder leerse sin miedo. MedTender te explica lo que dicen, te muestra dónde lo dicen y te ayuda a preparar las preguntas para tu médico.",
  pasos: [
    { titulo: "Sube una foto o un PDF", texto: "Un resultado de laboratorio, una orden, una fórmula o un informe. Si es una foto, buena luz y de frente." },
    { titulo: "Pulsa explícame este documento", texto: "Te cuenta de qué trata, lo que dice con su cita y qué significan los términos, en lenguaje sencillo." },
    { titulo: "Llévale las preguntas a tu médico", texto: "Te sugiere preguntas concretas. Las decisiones sobre tu salud las toma tu médico, no MedTender." },
  ],
  beneficios: [
    { titulo: "Explicaciones sencillas", texto: "Los términos técnicos se explican de forma general, sin decirte si tu valor es bueno o malo." },
    { titulo: "Siempre con la cita al lado", texto: "Cada punto muestra el texto exacto del documento del que sale." },
    { titulo: "Primero tu seguridad", texto: "Si describes una urgencia, el aviso de llamar al 123 aparece antes que cualquier otra cosa." },
    { titulo: "Tú decides sobre tus datos", texto: "Borras tu historial o tu cuenta completa con un botón." },
  ],
  preguntas: [
    { p: "¿MedTender me da un diagnóstico?", r: "No. Explica y cita lo que dice tu documento. No diagnostica, no receta y no indica dosis." },
    { p: "¿Qué pasa con mi documento después de subirlo?", r: "El archivo original se elimina del servidor después de leerlo. Guardamos fragmentos de texto y tus preguntas mientras tengas la cuenta." },
    { p: "¿Quién ve mis documentos?", r: "Solo tú. Cada cuenta personal es un espacio aparte, y confirmas tu correo para activarla." },
    { p: "¿Se envía mi información a otra empresa?", r: "Sí: el texto se envía a Google Gemini para leerlo, con los datos personales ocultos cuando aparecen con una etiqueta. Es una versión gratuita que Google puede usar para mejorar sus productos, así que sube solo lo necesario." },
    { p: "¿Cómo borro mi cuenta?", r: "Desde el menú de tu usuario, en «Eliminar mi cuenta». Se borra todo su contenido. Las copias de seguridad lo conservan hasta 14 días más." },
    { p: "¿Funciona con una foto del celular?", r: "Sí, con fotos de JPG, PNG y HEIC. Si la foto sale borrosa, te pedimos que la repitas con buena luz y de frente." },
  ],
  riesgo: {
    titulo: "Puedes borrarlo todo cuando quieras",
    texto: "Eliminas tu historial de preguntas o tu cuenta completa desde tu menú. El archivo original ya se eliminó del servidor al leerlo.",
  },
  cierre: "Entiende tus documentos antes de tu próxima cita.",
  alterna: { texto: "Para organizaciones", a: "/" },
};

export function PaginaBienvenida() {
  return <Landing c={ORGANIZACIONES} />;
}

export function PaginaPersonas() {
  return <Landing c={PERSONAS} />;
}

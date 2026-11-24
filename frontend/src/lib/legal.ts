/**
 * Quién responde por el tratamiento de los datos y cómo contactarlo. Se configura al construir la web
 * (VITE_RESPONSABLE y VITE_CONTACTO_PRIVACIDAD); sin configurar, el consentimiento no muestra esa línea.
 */
export const RESPONSABLE: string = import.meta.env.VITE_RESPONSABLE ?? "";
export const CONTACTO_PRIVACIDAD: string = import.meta.env.VITE_CONTACTO_PRIVACIDAD ?? "";

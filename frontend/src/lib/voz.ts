import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Lectura en voz alta con las voces del equipo. Solo se usan voces LOCALES (`localService`): algunos
 * navegadores ofrecen además voces en la nube, que enviarían el texto (información de salud) a un tercero.
 * Si no hay una voz local en español, no se lee.
 */
const PREFERIDAS = ["es-co", "es-419", "es-us", "es-mx", "es"];

export function vozLocalEnEspanol(voces: readonly SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  const idioma = (v: SpeechSynthesisVoice) => v.lang.toLowerCase().replace("_", "-");
  const locales = voces.filter((v) => v.localService === true && /^es($|-)/.test(idioma(v)));
  for (const preferida of PREFERIDAS) {
    const voz = locales.find((v) => idioma(v) === preferida);
    if (voz) return voz;
  }
  return locales[0] ?? null;
}

const MAXIMO = 220;

/** Frases cortas: con textos largos algunos navegadores cortan la lectura a los pocos segundos. */
export function trozos(texto: string): string[] {
  const partes: string[] = [];
  for (const frase of texto.split(/(?<=[.!?:;])\s+|\n+/)) {
    let actual = "";
    for (const palabra of frase.split(/\s+/).filter(Boolean)) {
      if (actual && actual.length + palabra.length + 1 > MAXIMO) {
        partes.push(actual);
        actual = palabra;
      } else {
        actual = actual ? `${actual} ${palabra}` : palabra;
      }
    }
    if (actual) partes.push(actual);
  }
  return partes;
}

const sintetizador = () =>
  typeof window !== "undefined" && "speechSynthesis" in window && window.speechSynthesis ? window.speechSynthesis : null;

export function useVoz() {
  const [voz, setVoz] = useState<SpeechSynthesisVoice | null>(() => vozLocalEnEspanol(sintetizador()?.getVoices() ?? []));
  const [leyendo, setLeyendo] = useState(false);
  const hablando = useRef(false);

  useEffect(() => {
    const s = sintetizador();
    if (!s) return;
    // Las voces llegan después de cargar la página en varios navegadores.
    const actualizar = () => setVoz(vozLocalEnEspanol(s.getVoices()));
    actualizar();
    s.addEventListener?.("voiceschanged", actualizar);
    return () => {
      s.removeEventListener?.("voiceschanged", actualizar);
      if (hablando.current) s.cancel();
    };
  }, []);

  const detener = useCallback(() => {
    hablando.current = false;
    setLeyendo(false);
    sintetizador()?.cancel();
  }, []);

  const leer = useCallback(
    (texto: string) => {
      const s = sintetizador();
      const partes = trozos(texto);
      if (!s || !voz || partes.length === 0) return;
      s.cancel();
      hablando.current = true;
      setLeyendo(true);
      const terminar = () => {
        hablando.current = false;
        setLeyendo(false);
      };
      partes.forEach((parte, i) => {
        const frase = new SpeechSynthesisUtterance(parte);
        frase.voice = voz;
        frase.lang = voz.lang;
        if (i === partes.length - 1) frase.onend = terminar;
        frase.onerror = terminar;
        s.speak(frase);
      });
    },
    [voz],
  );

  return { disponible: voz !== null, voz, leyendo, leer, detener };
}

import Lenis from "lenis";
import "lenis/dist/lenis.css";
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { mountScrollWorld, type SeccionMundo } from "../lib/scrollWorld";

/** Una parada del recorrido: la escena fija y el texto que la acompaña. */
export interface ParadaRecorrido {
  titulo: string;
  texto: string;
}

export interface PropsMundo {
  /** Titular de la portada: es el título de la primera escena. */
  titular: string;
  subtitular: string;
  cta: { texto: string; a: string };
  alterna: { texto: string; a: string };
  /** Seis paradas, en el orden de las escenas. La primera la reemplazan el titular y el subtitular. */
  paradas: ParadaRecorrido[];
}

const RUTA = "/recorrido";
const ETIQUETAS = ["Entrada", "Sala de espera", "Consultorio", "Laboratorio", "Rayos X", "Habitación"];

/**
 * Portada «scroll-world»: el hospital en miniatura ocupa toda la pantalla y el scroll mueve la cámara de
 * una escena a la siguiente con los tramos de video. Usa el motor de la skill scroll-world.
 */
export function MundoHospital({ titular, subtitular, cta, alterna, paradas }: PropsMundo) {
  const contenedor = useRef<HTMLDivElement>(null);
  const navegar = useRef(useNavigate());

  useEffect(() => {
    const el = contenedor.current;
    if (!el) return;
    const n = paradas.length;
    const secciones: SeccionMundo[] = paradas.map((p, i) => ({
      id: `escena-${i + 1}`,
      label: ETIQUETAS[i] ?? p.titulo,
      still: `${RUTA}/escena-${i + 1}.webp`,
      stillMobile: `${RUTA}/escena-${i + 1}-movil.webp`,
      eyebrow: i === 0 ? p.titulo : ETIQUETAS[i],
      title: i === 0 ? titular : p.titulo,
      body: i === 0 ? subtitular : p.texto,
      // La última escena dura más: el resto de la página sube por encima de ella al final.
      scroll: i === n - 1 ? 1.3 : undefined,
      cta:
        i === 0 || i === n - 1
          ? { primary: { label: cta.texto, href: cta.a }, secondary: { label: alterna.texto, href: alterna.a } }
          : undefined,
    }));
    return mountScrollWorld(el, {
      brand: { name: "MedTender", href: "/" },
      cta: { label: "Ingresar", href: "/ingreso" },
      hint: "Desliza para recorrer",
      diveScroll: 0.9,
      connScroll: 1.2,
      sections: secciones,
      connectors: paradas.slice(1).map((_, i) => `${RUTA}/tramo-${i + 1}.mp4`),
      navigate: (ruta) => navegar.current(ruta),
    });
  }, [titular, subtitular, cta.texto, cta.a, alterna.texto, alterna.a, paradas]);

  // Scroll con inercia (Lenis): la cámara del recorrido avanza suave en vez de a saltos de rueda.
  // Solo en esta página y nunca con movimiento reducido.
  useEffect(() => {
    if (typeof window.matchMedia !== "function" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const lenis = new Lenis({ lerp: 0.08, wheelMultiplier: 0.9 });
    let cuadro = requestAnimationFrame(function bucle(t) {
      lenis.raf(t);
      cuadro = requestAnimationFrame(bucle);
    });
    return () => {
      cancelAnimationFrame(cuadro);
      lenis.destroy();
    };
  }, []);

  return <div ref={contenedor} className="mundo-medtender" />;
}

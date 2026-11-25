export interface SeccionMundo {
  id?: string;
  label?: string;
  still?: string;
  stillMobile?: string;
  clip?: string;
  clipMobile?: string;
  accent?: string;
  scroll?: number;
  linger?: number;
  eyebrow?: string;
  title?: string;
  body?: string;
  tags?: string[];
  cta?: { primary?: { label: string; href: string }; secondary?: { label: string; href: string } };
}

export interface ConfigMundo {
  brand?: { name: string; href?: string };
  cta?: { label: string; href: string };
  diveScroll?: number;
  connScroll?: number;
  crossfade?: number;
  hint?: string;
  nav?: boolean;
  atmosphere?: boolean;
  sections: SeccionMundo[];
  connectors?: (string | null)[];
  connectorsMobile?: (string | null)[];
  /** Navegación interna de la SPA para los enlaces que empiezan con «/». */
  navigate?: (ruta: string) => void;
}

/** Monta el mundo dentro del contenedor y devuelve la función que lo desmonta por completo. */
export function mountScrollWorld(container: HTMLElement, config: ConfigMundo): () => void;

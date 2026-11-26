import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from "react";
import type { LucideIcon } from "../../iconos";
import { cn } from "../../lib/cn";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  etiqueta: string;
  icono?: LucideIcon;
  /** Contenido a la derecha (p. ej. el botón de mostrar contraseña). */
  extremo?: ReactNode;
};

/** Campo de texto con etiqueta visible, icono opcional y foco en el color de acción. */
export const Campo = forwardRef<HTMLInputElement, Props>(function Campo(
  { etiqueta, icono: Icono, extremo, className, id, ...resto },
  ref,
) {
  const generado = useId();
  const idCampo = id ?? generado;
  return (
    <div className={className}>
      <label htmlFor={idCampo} className="mb-2 block text-sm font-medium text-texto-2">
        {etiqueta}
      </label>
      <div
        className={cn(
          "group flex h-10 items-center gap-2 rounded-lg border border-borde bg-panel px-3 transition-[border-color,box-shadow] duration-300 ease-[var(--ease-salida)]",
          "focus-within:border-primario focus-within:shadow-[0_0_0_3px_color-mix(in_oklab,var(--primario)_22%,transparent)]",
        )}
      >
        {Icono && <Icono className="size-4 shrink-0 text-texto-3 transition-colors group-focus-within:text-primario" aria-hidden />}
        <input
          ref={ref}
          id={idCampo}
          className="h-full min-w-0 flex-1 bg-transparent text-base text-texto outline-none"
          {...resto}
        />
        {extremo}
      </div>
    </div>
  );
});

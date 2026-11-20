import type { LucideIcon } from "lucide-react";
import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "../../lib/cn";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  etiqueta: string;
  icono?: LucideIcon;
  /** Contenido a la derecha (p. ej. el botón de mostrar contraseña). */
  extremo?: ReactNode;
};

/** Campo de texto con etiqueta visible, icono opcional y foco en azul tinta. */
export const Campo = forwardRef<HTMLInputElement, Props>(function Campo(
  { etiqueta, icono: Icono, extremo, className, id, ...resto },
  ref,
) {
  const generado = useId();
  const idCampo = id ?? generado;
  return (
    <div className={className}>
      <label htmlFor={idCampo} className="mb-1.5 block text-[0.85rem] font-medium text-tinta-2">
        {etiqueta}
      </label>
      <div
        className={cn(
          "group flex h-11 items-center gap-2.5 rounded-md border border-tinta/35 bg-folio px-3 transition-[border-color,box-shadow] duration-200",
          "focus-within:border-accion focus-within:shadow-[0_0_0_3px_color-mix(in_oklab,var(--accion)_22%,transparent)]",
        )}
      >
        {Icono && (
          <Icono className="size-[1.1rem] shrink-0 text-tinta-3 transition-colors group-focus-within:text-accion" aria-hidden />
        )}
        <input
          ref={ref}
          id={idCampo}
          className="h-full min-w-0 flex-1 bg-transparent text-[0.95rem] text-tinta outline-none"
          {...resto}
        />
        {extremo}
      </div>
    </div>
  );
});

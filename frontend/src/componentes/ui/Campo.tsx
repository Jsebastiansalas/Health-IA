import type { LucideIcon } from "lucide-react";
import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "../../lib/cn";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  etiqueta: string;
  icono?: LucideIcon;
  /** Contenido a la derecha (p. ej. el botón de mostrar contraseña). */
  extremo?: ReactNode;
};

/** Campo de texto con etiqueta, icono opcional y foco cian. */
export const Campo = forwardRef<HTMLInputElement, Props>(function Campo(
  { etiqueta, icono: Icono, extremo, className, id, ...resto },
  ref,
) {
  const generado = useId();
  const idCampo = id ?? generado;
  return (
    <div className={className}>
      <label htmlFor={idCampo} className="mb-1.5 block pl-5 text-[0.8rem] font-normal text-tx-2">
        {etiqueta}
      </label>
      <div
        className={cn(
          "group flex h-12 items-center gap-2.5 rounded-full border border-ink/45 bg-transparent px-5 transition-[border-color,box-shadow] duration-200",
          "focus-within:border-ink",
        )}
      >
        {Icono && (
          <Icono className="size-[1.1rem] shrink-0 text-tx-3 transition-colors group-focus-within:text-hema" aria-hidden />
        )}
        <input
          ref={ref}
          id={idCampo}
          className="h-full min-w-0 flex-1 bg-transparent text-[0.95rem] text-tx outline-none"
          {...resto}
        />
        {extremo}
      </div>
    </div>
  );
});

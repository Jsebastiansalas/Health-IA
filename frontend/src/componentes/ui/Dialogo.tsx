import * as Dialog from "@radix-ui/react-dialog";
import { X } from "../../iconos";
import type { ReactNode } from "react";
import { cn } from "../../lib/cn";

type Props = {
  abierto: boolean;
  alCambiar: (abierto: boolean) => void;
  titulo: string;
  descripcion?: string;
  children: ReactNode;
  /** `lateral`: panel que entra por la derecha. `centro`: ventana centrada. */
  tipo?: "lateral" | "centro";
};

/** Diálogo accesible (foco atrapado, Escape, etiquetas) sobre Radix. */
export function Dialogo({ abierto, alCambiar, titulo, descripcion, children, tipo = "lateral" }: Props) {
  return (
    <Dialog.Root open={abierto} onOpenChange={alCambiar}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-texto/55 data-[state=open]:animate-[aparecer_300ms_var(--ease-salida)]" />
        <Dialog.Content
          className={cn(
            "panel fixed z-50 flex flex-col overflow-hidden outline-none",
            tipo === "lateral"
              ? "inset-y-0 right-0 w-full max-w-md rounded-l-md data-[state=open]:animate-[aparecer_350ms_var(--ease-salida)]"
              : "left-1/2 top-1/2 w-[min(92vw,34rem)] -translate-x-1/2 -translate-y-1/2 rounded-lg",
          )}
        >
          <div className="flex items-start justify-between gap-4 border-b border-borde px-6 py-4">
            <div>
              <Dialog.Title className="text-xl">{titulo}</Dialog.Title>
              {descripcion && (
                <Dialog.Description className="mt-1 text-sm text-texto-2">{descripcion}</Dialog.Description>
              )}
            </div>
            <Dialog.Close
              className="grid size-8 shrink-0 place-items-center rounded-lg text-texto-2 transition-colors hover:bg-texto/10 hover:text-texto"
              aria-label="Cerrar"
            >
              <X className="size-5" />
            </Dialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

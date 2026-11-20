import * as Menu from "@radix-ui/react-dropdown-menu";
import { ChevronsUpDown, FolderOpen, LogOut, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { Toaster } from "sonner";
import { cn } from "../lib/cn";
import { useSesion } from "../sesion";
import { Tejido } from "../arte/Tejido";
import { Marca } from "./Marca";

export const ROLES: Record<string, string> = {
  ADMIN_TENANT: "Administración",
  JURIDICO: "Jurídico",
  AUDITOR_MEDICO: "Auditoría médica",
  BIOMEDICO: "Ingeniería biomédica",
  LECTOR: "Lectura",
};

const iniciales = (nombre?: string) =>
  (nombre ?? "?")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");

function Avatar({ nombre, className }: { nombre?: string; className?: string }) {
  return (
    <span
      className={cn(
        "grid size-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-eosina to-hema font-display text-sm font-bold text-white",
        className,
      )}
      aria-hidden
    >
      {iniciales(nombre)}
    </span>
  );
}

function MenuUsuario({ compacto = false }: { compacto?: boolean }) {
  const { usuario, salir } = useSesion();
  return (
    <Menu.Root>
      <Menu.Trigger
        className={cn(
          "group flex w-full items-center gap-3 rounded-2xl border border-white/15 bg-white/[0.07] p-2.5 text-left text-white transition-colors hover:bg-white/[0.14]",
          compacto && "w-auto border-0 bg-transparent p-1 text-tx",
        )}
        aria-label="Menú de usuario"
      >
        <Avatar nombre={usuario?.nombre_completo} />
        {!compacto && (
          <>
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block truncate text-sm font-semibold">{usuario?.nombre_completo ?? "…"}</span>
              <span className="block truncate text-xs text-white/65">{usuario ? ROLES[usuario.rol_global] : ""}</span>
            </span>
            <ChevronsUpDown className="size-4 text-white/60 transition-colors group-hover:text-white" aria-hidden />
          </>
        )}
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content
          side={compacto ? "bottom" : "top"}
          align={compacto ? "end" : "start"}
          sideOffset={8}
          className="vidrio-solido z-50 w-60 rounded-2xl p-1.5 text-sm data-[state=open]:animate-[aparecer_220ms_var(--ease-salida)]"
        >
          <div className="px-3 py-2.5">
            <p className="truncate font-semibold">{usuario?.nombre_completo}</p>
            <p className="truncate text-xs text-tx-3">{usuario?.email}</p>
          </div>
          <Menu.Separator className="my-1 h-px bg-ink/10" />
          <Menu.Item
            onSelect={salir}
            className="flex cursor-pointer items-center gap-2.5 rounded-xl px-3 py-2.5 text-tx-2 outline-none transition-colors data-[highlighted]:bg-ink/8 data-[highlighted]:text-tx"
          >
            <LogOut className="size-4" aria-hidden />
            Cerrar sesión
          </Menu.Item>
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}

const enlaceNav = ({ isActive }: { isActive: boolean }) =>
  cn(
    "flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-colors",
    isActive ? "bg-eosina text-white shadow-[0_10px_22px_-12px_rgb(217_48_111/0.9)]" : "text-white/75 hover:bg-white/10 hover:text-white",
  );

export function Marco({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen lg:pl-72">
      {/* Lavado de tejido muy tenue: da identidad al fondo sin competir con el contenido. */}
      <div
        className="pointer-events-none fixed inset-x-0 top-0 -z-10 h-[26rem] [mask-image:linear-gradient(to_bottom,black_0%,transparent_85%)]"
        aria-hidden
      >
        <Tejido semilla={3} celula={64} tinte={0.3} lavanda={0.5} />
      </div>

      {/* Barra lateral (escritorio) */}
      <aside className="fixed inset-y-3 left-3 z-30 hidden w-64 flex-col rounded-3xl bg-hema-pro p-4 text-white shadow-[0_30px_60px_-30px_rgb(28_23_82/0.8)] lg:flex">
        <NavLink to="/" className="px-2 pb-5 pt-2" aria-label="MedTender, inicio">
          <Marca oscuro />
        </NavLink>
        <nav className="flex-1 space-y-1" aria-label="Principal">
          <NavLink to="/" end className={enlaceNav}>
            <FolderOpen className="size-[1.15rem]" aria-hidden />
            Expedientes
          </NavLink>
        </nav>
        <div className="mb-3 rounded-2xl border border-white/15 bg-white/[0.07] p-3.5 text-[0.8rem] leading-relaxed text-white/80">
          <ShieldCheck className="mb-1.5 size-5 text-eosina-clara" aria-hidden />
          Tus PDF se eliminan del servidor al indexarlos. Los originales se abren desde tu equipo.
        </div>
        <MenuUsuario />
      </aside>

      {/* Barra superior (móvil y tableta) */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-ink/10 bg-white/90 px-4 py-2.5 backdrop-blur lg:hidden">
        <NavLink to="/" aria-label="MedTender, inicio">
          <Marca />
        </NavLink>
        <MenuUsuario compacto />
      </header>

      <main className="mx-auto max-w-[1400px] px-4 py-7 sm:px-8 lg:py-10">{children}</main>
      <Toaster
        theme="light"
        position="bottom-right"
        toastOptions={{
          classNames: {
            toast: "!border !border-ink/10 !bg-white !text-tx !shadow-2xl !rounded-2xl",
            description: "!text-tx-2",
          },
        }}
      />
    </div>
  );
}

import * as Menu from "@radix-ui/react-dropdown-menu";
import { ChevronsUpDown, FolderOpen, LogOut, Pill, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { Toaster } from "sonner";
import { cn } from "../lib/cn";
import { useSesion } from "../sesion";
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
        "grid size-10 shrink-0 place-items-center rounded-full bg-obsidiana font-display text-sm font-[480] text-tx",
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
          "group flex w-full items-center gap-3 rounded-full bg-obsidiana p-2 text-left text-tx transition-colors hover:bg-ink/[0.12]",
          compacto && "w-auto border-0 bg-transparent p-1 text-tx",
        )}
        aria-label="Menú de usuario"
      >
        <Avatar nombre={usuario?.nombre_completo} />
        {!compacto && (
          <>
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block truncate text-sm font-semibold">{usuario?.nombre_completo ?? "…"}</span>
              <span className="block truncate text-xs text-tx-2">{usuario ? ROLES[usuario.rol_global] : ""}</span>
            </span>
            <ChevronsUpDown className="size-4 text-tx-3 transition-colors group-hover:text-tx" aria-hidden />
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
            className="flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2.5 text-tx-2 outline-none transition-colors data-[highlighted]:bg-ink/8 data-[highlighted]:text-tx"
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
    "flex items-center gap-3 rounded-full px-4 py-2.5 text-sm font-normal transition-colors",
    isActive ? "bg-obsidiana text-tx" : "text-tx-2 hover:bg-ink/[0.06] hover:text-tx",
  );

export function Marco({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen lg:pl-72">
      {/* Barra lateral (escritorio) */}
      <aside className="fixed inset-y-3 left-3 z-30 hidden w-64 flex-col rounded-xl bg-panel p-4 text-tx lg:flex">
        <NavLink to="/" className="px-2 pb-5 pt-2" aria-label="MedTender, inicio">
          <Marca />
        </NavLink>
        <nav className="flex-1 space-y-1" aria-label="Principal">
          <NavLink to="/" end className={enlaceNav}>
            <FolderOpen className="size-[1.15rem]" aria-hidden />
            Expedientes
          </NavLink>
          <NavLink to="/medicamentos" className={enlaceNav}>
            <Pill className="size-[1.15rem]" aria-hidden />
            Medicamentos
          </NavLink>
        </nav>
        <div className="mb-3 rounded-xl bg-obsidiana p-3.5 text-[0.8rem] leading-relaxed text-tx-2">
          <ShieldCheck className="mb-1.5 size-5 text-tx-2" aria-hidden />
          Tus PDF se eliminan del servidor al indexarlos. Los originales se abren desde tu equipo.
        </div>
        <MenuUsuario />
      </aside>

      {/* Barra superior (móvil y tableta) */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-ink/10 bg-sala px-4 py-2.5 lg:hidden">
        <NavLink to="/" aria-label="MedTender, inicio">
          <Marca />
        </NavLink>
        <NavLink to="/medicamentos" className="ml-auto mr-2 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm text-tx-2 hover:bg-ink/10 hover:text-tx">
          <Pill className="size-4" aria-hidden />
          Medicamentos
        </NavLink>
        <MenuUsuario compacto />
      </header>

      <main className="mx-auto max-w-[1400px] px-4 py-7 sm:px-8 lg:py-10">{children}</main>
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          classNames: {
            toast: "!border-0 !bg-obsidiana !text-tx !shadow-none !rounded-xl",
            description: "!text-tx-2",
          },
        }}
      />
    </div>
  );
}

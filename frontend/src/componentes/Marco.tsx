import * as Menu from "@radix-ui/react-dropdown-menu";
import { ChevronsUpDown, FolderOpen, LogOut, Moon, Pill, ShieldCheck, Sun, Trash2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { Toaster } from "sonner";
import { cn } from "../lib/cn";
import { useTema } from "../lib/tema";
import { useSesion } from "../sesion";
import { useConsentimiento } from "../lib/consentimiento";
import { Marca } from "./Marca";
import { DialogoEliminarCuenta } from "./Privacidad";

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
        "grid size-10 shrink-0 place-items-center rounded-md bg-folio font-display text-sm font-semibold text-tinta",
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
  const { tema, alternar } = useTema();
  const { esPersonal } = useConsentimiento();
  const [eliminando, setEliminando] = useState(false);
  return (
    <>
    <Menu.Root>
      <Menu.Trigger
        className={cn(
          "group flex w-full items-center gap-3 rounded-md bg-carpeta-osc/45 p-2 text-left text-tinta transition-colors hover:bg-carpeta-osc/70",
          compacto && "w-auto border-0 bg-transparent p-1 text-tinta",
        )}
        aria-label="Menú de usuario"
      >
        <Avatar nombre={usuario?.nombre_completo} />
        {!compacto && (
          <>
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block truncate text-sm font-semibold">{usuario?.nombre_completo ?? "…"}</span>
              <span className="block truncate text-xs text-tinta-2">{usuario ? ROLES[usuario.rol_global] : ""}</span>
            </span>
            <ChevronsUpDown className="size-4 text-tinta-3 transition-colors group-hover:text-tinta" aria-hidden />
          </>
        )}
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content
          side={compacto ? "bottom" : "top"}
          align={compacto ? "end" : "start"}
          sideOffset={8}
          className="folio z-50 w-60 rounded-md p-1.5 text-sm data-[state=open]:animate-[aparecer_220ms_var(--ease-salida)]"
        >
          <div className="px-3 py-2.5">
            <p className="truncate font-semibold">{usuario?.nombre_completo}</p>
            <p className="truncate text-xs text-tinta-3">{usuario?.email}</p>
          </div>
          <Menu.Separator className="my-1 h-px bg-tinta/10" />
          <Menu.Item
            onSelect={alternar}
            className="flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2.5 text-tinta-2 outline-none transition-colors data-[highlighted]:bg-tinta/8 data-[highlighted]:text-tinta"
          >
            {tema === "papel" ? <Moon className="size-4" aria-hidden /> : <Sun className="size-4" aria-hidden />}
            {tema === "papel" ? "Tema nocturno" : "Tema papel"}
          </Menu.Item>
          <Menu.Item
            onSelect={salir}
            className="flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2.5 text-tinta-2 outline-none transition-colors data-[highlighted]:bg-tinta/8 data-[highlighted]:text-tinta"
          >
            <LogOut className="size-4" aria-hidden />
            Cerrar sesión
          </Menu.Item>
          {esPersonal && (
            <Menu.Item
              onSelect={() => setEliminando(true)}
              className="flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2.5 text-peligro outline-none transition-colors data-[highlighted]:bg-peligro/10"
            >
              <Trash2 className="size-4" aria-hidden />
              Eliminar mi cuenta
            </Menu.Item>
          )}
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
    {esPersonal && <DialogoEliminarCuenta abierto={eliminando} alCambiar={setEliminando} />}
    </>
  );
}

const enlaceNav = ({ isActive }: { isActive: boolean }) =>
  cn(
    "flex items-center gap-3 rounded-md px-3.5 py-2.5 text-sm font-medium transition-colors",
    isActive ? "bg-folio text-tinta shadow-folio" : "text-tinta/80 hover:bg-tinta/[0.08] hover:text-tinta",
  );

export function Marco({ children }: { children: ReactNode }) {
  const { tema } = useTema();
  return (
    <div className="relative min-h-screen lg:pl-72">
      {/* Barra lateral (escritorio) */}
      <aside className="fixed inset-y-3 left-3 z-30 hidden w-64 flex-col rounded-md bg-carpeta p-4 text-tinta lg:flex">
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
        <div className="mb-3 rounded-md bg-carpeta-osc/45 p-3.5 text-[0.8rem] leading-relaxed text-tinta">
          <ShieldCheck className="mb-1.5 size-5" aria-hidden />
          Licitaciones, historias clínicas y medicamentos. Cada respuesta cita su fuente.
        </div>
        <MenuUsuario />
      </aside>

      {/* Barra superior (móvil y tableta) */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-tinta/15 bg-carpeta px-4 py-2.5 lg:hidden">
        <NavLink to="/" aria-label="MedTender, inicio">
          <Marca />
        </NavLink>
        <NavLink to="/medicamentos" className="ml-auto mr-2 inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-tinta-2 hover:bg-tinta/10 hover:text-tinta">
          <Pill className="size-4" aria-hidden />
          Medicamentos
        </NavLink>
        <MenuUsuario compacto />
      </header>

      <main className="mx-auto max-w-[1400px] px-4 py-7 sm:px-8 lg:py-10">{children}</main>
      <Toaster
        theme={tema === "nocturno" ? "dark" : "light"}
        position="bottom-right"
        toastOptions={{
          classNames: {
            toast: "!border-0 !bg-folio !text-tinta !shadow-folio !rounded-md",
            description: "!text-tinta-2",
          },
        }}
      />
    </div>
  );
}

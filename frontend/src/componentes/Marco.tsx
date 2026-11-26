import * as Menu from "@radix-ui/react-dropdown-menu";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { Toaster } from "sonner";
import { Bell, ChevronsUpDown, DownloadSimple, FolderOpen, LogOut, Moon, Pill, ShieldCheck, Sun, TextAa, Trash2 } from "../iconos";
import { EVENTO_DOS_PASOS_REQUERIDO } from "../api/cliente";
import { toast as avisar } from "sonner";
import { cn } from "../lib/cn";
import { useCompartido } from "../lib/compartido";
import { useConsentimiento } from "../lib/consentimiento";
import { useTema } from "../lib/tema";
import { useSesion } from "../sesion";
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
      className={cn("grid size-8 shrink-0 place-items-center rounded-lg bg-marino text-xs font-semibold text-white", className)}
      aria-hidden
    >
      {iniciales(nombre)}
    </span>
  );
}

const itemMenu =
  "flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm text-texto-2 outline-none transition-colors duration-300 data-[highlighted]:bg-panel-2 data-[highlighted]:text-texto";

function MenuUsuario() {
  const { usuario, salir } = useSesion();
  const { tema, alternar } = useTema();
  const { esPersonal } = useConsentimiento();
  const [eliminando, setEliminando] = useState(false);
  const navegar = useNavigate();
  // Un administrador sin verificación en dos pasos (si es obligatoria) va directo a activarla.
  useEffect(() => {
    const ir = () => {
      avisar.info("Activa la verificación en dos pasos para seguir usando MedTender.");
      navegar("/cuenta/seguridad");
    };
    window.addEventListener(EVENTO_DOS_PASOS_REQUERIDO, ir);
    return () => window.removeEventListener(EVENTO_DOS_PASOS_REQUERIDO, ir);
  }, [navegar]);
  return (
    <>
      <Menu.Root>
        <Menu.Trigger
          className="group flex items-center gap-2 rounded-lg p-1 pr-2 text-left transition-colors duration-300 hover:bg-panel-2"
          aria-label="Menú de usuario"
        >
          <Avatar nombre={usuario?.nombre_completo} />
          <span className="hidden min-w-0 leading-tight sm:block">
            <span className="block max-w-40 truncate text-sm font-medium">{usuario?.nombre_completo ?? "…"}</span>
            <span className="block max-w-40 truncate text-xs text-texto-3">{usuario ? (esPersonal ? "Cuenta personal" : ROLES[usuario.rol_global]) : ""}</span>
          </span>
          <ChevronsUpDown className="size-4 text-texto-3 transition-colors group-hover:text-texto" aria-hidden />
        </Menu.Trigger>
        <Menu.Portal>
          <Menu.Content
            align="end"
            sideOffset={8}
            className="panel z-50 w-60 p-2 text-sm shadow-lg data-[state=open]:animate-[aparecer_300ms_var(--ease-salida)]"
          >
            <div className="px-3 py-2">
              <p className="truncate text-sm font-semibold">{usuario?.nombre_completo}</p>
              <p className="truncate text-xs text-texto-3">{usuario?.email}</p>
            </div>
            <Menu.Separator className="my-2 h-px bg-borde" />
            <Menu.Item onSelect={alternar} className={itemMenu}>
              {tema === "claro" ? <Moon className="size-4" aria-hidden /> : <Sun className="size-4" aria-hidden />}
              {tema === "claro" ? "Tema oscuro" : "Tema claro"}
            </Menu.Item>
            <Menu.Item onSelect={() => navegar("/cuenta/accesibilidad")} className={itemMenu}>
              <TextAa className="size-4" aria-hidden />
              Accesibilidad
            </Menu.Item>
            <Menu.Item onSelect={() => navegar("/cuenta/seguridad")} className={itemMenu}>
              <ShieldCheck className="size-4" aria-hidden />
              Seguridad de la cuenta
            </Menu.Item>
            {esPersonal && (
              <Menu.Item onSelect={() => navegar("/cuenta/datos")} className={itemMenu}>
                <DownloadSimple className="size-4" aria-hidden />
                Mis datos
              </Menu.Item>
            )}
            <Menu.Item onSelect={salir} className={itemMenu}>
              <LogOut className="size-4" aria-hidden />
              Cerrar sesión
            </Menu.Item>
            {esPersonal && (
              <Menu.Item
                onSelect={() => setEliminando(true)}
                className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm text-peligro outline-none transition-colors duration-300 data-[highlighted]:bg-peligro/10"
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
    "relative flex h-12 items-center gap-2 px-1 text-sm font-medium transition-colors duration-300",
    "after:absolute after:inset-x-1 after:bottom-0 after:h-0.5 after:rounded-full after:bg-primario after:transition-opacity after:duration-300",
    isActive ? "text-texto after:opacity-100" : "text-texto-2 after:opacity-0 hover:text-texto",
  );

/** Si quedó un archivo de «Compartir» sin subir (p. ej. había que ingresar primero), se ofrece retomarlo. */
function AvisoCompartido() {
  const { archivo } = useCompartido();
  const { pathname } = useLocation();
  if (!archivo || pathname === "/compartir") return null;
  return (
    <p role="status" className="panel mb-6 flex flex-wrap items-center justify-between gap-3 p-4 text-sm">
      <span>Tienes un archivo compartido sin subir: {archivo.name || "archivo"}.</span>
      <Link to="/compartir" className="font-medium text-primario-osc underline underline-offset-4">
        Elegir expediente
      </Link>
    </p>
  );
}

export function Marco({ children }: { children: ReactNode }) {
  const { tema } = useTema();
  const contenido = useRef<HTMLElement>(null);
  const { pathname } = useLocation();
  const anterior = useRef(pathname);
  useEffect(() => {
    if (anterior.current === pathname) return;
    anterior.current = pathname;
    contenido.current?.focus({ preventScroll: true });
  }, [pathname]);
  return (
    <div className="min-h-screen">
      <a
        href="#contenido"
        className="sr-only rounded-lg bg-primario px-4 py-2 text-sm font-semibold text-primario-tx focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50"
      >
        Saltar al contenido
      </a>
      <header className="sticky top-0 z-30 border-b border-borde bg-panel/90 backdrop-blur">
        <div className="mx-auto flex h-12 max-w-[1400px] items-center gap-6 px-4 sm:px-8">
          <NavLink to="/" aria-label="MedTender, inicio" className="shrink-0">
            <Marca compacta className="sm:hidden" />
            <Marca className="hidden sm:inline-flex" />
          </NavLink>
          <nav className="flex flex-1 items-center gap-3 sm:gap-6" aria-label="Principal">
            <NavLink to="/" end className={enlaceNav}>
              <FolderOpen className="size-4" aria-hidden />
              <span className="hidden sm:inline">Expedientes</span>
              <span className="sr-only sm:hidden">Expedientes</span>
            </NavLink>
            <NavLink to="/medicamentos" className={enlaceNav}>
              <Pill className="size-4" aria-hidden />
              <span className="hidden sm:inline">Medicamentos</span>
              <span className="sr-only sm:hidden">Medicamentos</span>
            </NavLink>
            <NavLink to="/recordatorios" className={enlaceNav}>
              <Bell className="size-4" aria-hidden />
              <span className="hidden sm:inline">Recordatorios</span>
              <span className="sr-only sm:hidden">Recordatorios</span>
            </NavLink>
          </nav>
          <MenuUsuario />
        </div>
      </header>

      <main id="contenido" ref={contenido} tabIndex={-1} className="outline-none mx-auto max-w-[1400px] px-4 py-8 sm:px-8 lg:py-10">
        <AvisoCompartido />
        {children}
      </main>
      <Toaster
        theme={tema === "oscuro" ? "dark" : "light"}
        position="bottom-right"
        toastOptions={{
          classNames: {
            toast: "!border !border-borde !bg-panel !text-texto !shadow-lg !rounded-xl",
            description: "!text-texto-2",
          },
        }}
      />
    </div>
  );
}

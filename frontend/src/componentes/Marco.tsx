import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useSesion } from "../sesion";

const ROLES: Record<string, string> = {
  ADMIN_TENANT: "Administración",
  JURIDICO: "Jurídico",
  AUDITOR_MEDICO: "Auditoría médica",
  BIOMEDICO: "Ingeniería biomédica",
  LECTOR: "Lectura",
};

export function Marca({ grande = false }: { grande?: boolean }) {
  return (
    <span className={`font-display tracking-tight ${grande ? "text-4xl" : "text-xl"}`}>
      <span className="italic" style={{ fontVariationSettings: '"SOFT" 100, "WONK" 1' }}>
        Med
      </span>
      <span className="font-semibold">Tender</span>
      <span className="ml-1 align-super font-mono text-[0.55em] text-sello">RAG</span>
    </span>
  );
}

export function Marco({ children }: { children: ReactNode }) {
  const { usuario, salir } = useSesion();
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-papel-3 bg-papel/85 backdrop-blur">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between px-6 py-3">
          <Link to="/" className="flex items-baseline gap-4">
            <Marca />
            <span className="etiqueta hidden md:inline">Archivo de expedientes</span>
          </Link>
          <div className="flex items-center gap-5 text-sm">
            {usuario && (
              <div className="text-right leading-tight">
                <div className="font-medium">{usuario.nombre_completo}</div>
                <div className="etiqueta">{ROLES[usuario.rol_global]}</div>
              </div>
            )}
            <button className="boton boton-linea" onClick={salir}>
              Salir
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1500px] px-6 py-8">{children}</main>
    </div>
  );
}

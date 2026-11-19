import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, EVENTO_SESION_EXPIRADA, guardarTokens, haySesion, post } from "./api/cliente";
import type { Tokens, Usuario } from "./api/tipos";

interface Sesion {
  usuario: Usuario | undefined;
  autenticado: boolean;
  ingresar: (email: string, password: string) => Promise<void>;
  salir: () => void;
}

const Contexto = createContext<Sesion | null>(null);

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const cliente = useQueryClient();
  const [autenticado, setAutenticado] = useState(haySesion);
  const { data: usuario } = useQuery({
    queryKey: ["yo"],
    queryFn: () => api<Usuario>("/auth/me"),
    enabled: autenticado,
    staleTime: 5 * 60_000,
  });

  const salir = useCallback(() => {
    guardarTokens(null);
    cliente.clear();
    setAutenticado(false);
  }, [cliente]);

  useEffect(() => {
    window.addEventListener(EVENTO_SESION_EXPIRADA, salir);
    return () => window.removeEventListener(EVENTO_SESION_EXPIRADA, salir);
  }, [salir]);

  const ingresar = useCallback(async (email: string, password: string) => {
    guardarTokens(await post<Tokens>("/auth/login", { email, password }));
    setAutenticado(true);
  }, []);

  return <Contexto.Provider value={{ usuario, autenticado, ingresar, salir }}>{children}</Contexto.Provider>;
}

export function useSesion(): Sesion {
  const s = useContext(Contexto);
  if (!s) throw new Error("useSesion fuera de ProveedorSesion");
  return s;
}

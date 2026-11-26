import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, EVENTO_SESION_EXPIRADA, guardarTokens, haySesion, post, refreshActual } from "./api/cliente";
import type { RespuestaIngreso, Tokens, Usuario } from "./api/tipos";
import { olvidarDispositivo } from "./lib/notificaciones";

interface Sesion {
  usuario: Usuario | undefined;
  autenticado: boolean;
  /** Devuelve el desafío si la cuenta pide el segundo paso; si no, ya quedó la sesión abierta. */
  ingresar: (email: string, password: string) => Promise<{ desafio?: string }>;
  verificarDosPasos: (desafio: string, codigo: string) => Promise<void>;
  /** Guarda tokens nuevos (tras cambiar la contraseña o cerrar las demás sesiones). */
  renovarTokens: (t: Tokens) => void;
  registrarPersonal: (nombre: string, email: string, password: string) => Promise<void>;
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
    // Cierra la sesión también en el servidor: su token de renovación deja de servir.
    const refresh = refreshActual();
    if (refresh) void post("/auth/logout", { refresh_token: refresh }).catch(() => {});
    void olvidarDispositivo(); // que no sigan llegando avisos de una sesión cerrada
    guardarTokens(null);
    cliente.clear();
    setAutenticado(false);
  }, [cliente]);

  useEffect(() => {
    window.addEventListener(EVENTO_SESION_EXPIRADA, salir);
    return () => window.removeEventListener(EVENTO_SESION_EXPIRADA, salir);
  }, [salir]);

  const ingresar = useCallback(async (email: string, password: string) => {
    const r = await post<RespuestaIngreso>("/auth/login", { email, password });
    if (r.requiere2fa && r.desafio) return { desafio: r.desafio };
    guardarTokens(r as Tokens);
    setAutenticado(true);
    return {};
  }, []);

  const verificarDosPasos = useCallback(async (desafio: string, codigo: string) => {
    guardarTokens(await post<Tokens>("/auth/2fa/verificar", { desafio, codigo }));
    setAutenticado(true);
  }, []);

  const renovarTokens = useCallback(
    (t: Tokens) => {
      guardarTokens(t);
      void cliente.invalidateQueries({ queryKey: ["yo"] });
    },
    [cliente],
  );

  const registrarPersonal = useCallback(async (nombre: string, email: string, password: string) => {
    guardarTokens(await post<Tokens>("/auth/registro-personal", { nombre, email, password }));
    setAutenticado(true);
  }, []);

  return (
    <Contexto.Provider value={{ usuario, autenticado, ingresar, verificarDosPasos, renovarTokens, registrarPersonal, salir }}>
      {children}
    </Contexto.Provider>
  );
}

export function useSesion(): Sesion {
  const s = useContext(Contexto);
  if (!s) throw new Error("useSesion fuera de ProveedorSesion");
  return s;
}

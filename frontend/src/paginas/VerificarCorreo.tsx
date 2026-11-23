import { CheckCircle2, MailWarning } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { post } from "../api/cliente";
import { Marca } from "../componentes/Marca";
import { Boton } from "../componentes/ui/Boton";

type Estado = { fase: "verificando" } | { fase: "ok" } | { fase: "error"; mensaje: string };

/** Página a la que lleva el enlace del correo: no necesita sesión, el token del enlace es la credencial. */
export function PaginaVerificarCorreo() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [estado, setEstado] = useState<Estado>(token ? { fase: "verificando" } : { fase: "error", mensaje: "El enlace no trae el código de verificación." });

  useEffect(() => {
    if (!token) return;
    let activo = true;
    post<{ verificado: boolean }>("/auth/verificar-correo", { token })
      .then(() => activo && setEstado({ fase: "ok" }))
      .catch((e: unknown) =>
        activo && setEstado({ fase: "error", mensaje: e instanceof Error ? e.message : "No se pudo verificar el correo." }),
      );
    return () => {
      activo = false;
    };
  }, [token]);

  return (
    <main className="mx-auto grid min-h-screen max-w-lg content-center gap-6 px-6">
      <Marca />
      {estado.fase === "verificando" && <p role="status">Confirmando tu correo…</p>}
      {estado.fase === "ok" && (
        <section aria-live="polite" className="folio p-6">
          <h1 className="flex items-center gap-2.5 text-[1.4rem]">
            <CheckCircle2 className="size-6 text-ok" aria-hidden />
            Correo confirmado
          </h1>
          <p className="mt-2 text-tinta-2">Ya puedes usar tu cuenta. Ingresa para continuar.</p>
          <Link to="/ingreso" className="mt-5 inline-block">
            <Boton variante="primario">Ingresar</Boton>
          </Link>
        </section>
      )}
      {estado.fase === "error" && (
        <section role="alert" className="folio p-6">
          <h1 className="flex items-center gap-2.5 text-[1.4rem]">
            <MailWarning className="size-6 text-aviso" aria-hidden />
            No pudimos confirmar tu correo
          </h1>
          <p className="mt-2 text-tinta-2">{estado.mensaje}</p>
          <p className="mt-2 text-[0.9rem] text-tinta-3">Ingresa a tu cuenta y pide un enlace nuevo desde el aviso que verás arriba.</p>
          <Link to="/ingreso" className="mt-5 inline-block">
            <Boton>Ir a ingresar</Boton>
          </Link>
        </section>
      )}
    </main>
  );
}

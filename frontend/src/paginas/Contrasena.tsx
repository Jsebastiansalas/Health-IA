import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { post } from "../api/cliente";
import { Marca } from "../componentes/Marca";
import { Boton } from "../componentes/ui/Boton";
import { Campo } from "../componentes/ui/Campo";
import { AlertCircle, CheckCircle2, LockKeyhole, Mail } from "../iconos";

function Hoja({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <main className="mx-auto grid min-h-[100svh] max-w-md content-center gap-6 px-6 py-10">
      <Link to="/" aria-label="MedTender, inicio" className="w-fit">
        <Marca />
      </Link>
      <section className="panel p-6 sm:p-8">
        <h1 className="text-2xl font-semibold">{titulo}</h1>
        {children}
      </section>
    </main>
  );
}

function Aviso({ texto }: { texto: string }) {
  return (
    <p role="alert" className="flex items-start gap-3 rounded-lg border border-peligro/40 bg-peligro/10 px-4 py-3 text-sm text-peligro">
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
      {texto}
    </p>
  );
}

/** «Olvidé mi contraseña»: siempre la misma respuesta, exista o no la cuenta. */
export function PaginaOlvideContrasena() {
  const [email, setEmail] = useState("");
  const [enviado, setEnviado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await post("/auth/olvide-contrasena", { email: email.trim() });
      setEnviado(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo enviar el enlace.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Hoja titulo="Restablece tu contraseña">
      {enviado ? (
        <div role="status" className="mt-4 space-y-3 text-texto-2">
          <p className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-ok" aria-hidden />
            Si hay una cuenta con ese correo, te enviamos un enlace. Vence en 30 minutos y sirve una sola vez.
          </p>
          <p className="text-sm text-texto-3">Si no llega en unos minutos, revisa la carpeta de correo no deseado.</p>
          <Link to="/ingreso" className="inline-block text-sm font-medium text-primario-osc underline underline-offset-4">
            Volver a ingresar
          </Link>
        </div>
      ) : (
        <form onSubmit={enviar} className="mt-6 space-y-4" noValidate>
          <p className="text-sm text-texto-2">Escribe el correo de tu cuenta y te enviaremos un enlace para elegir una contraseña nueva.</p>
          <Campo
            etiqueta="Correo electrónico"
            icono={Mail}
            type="email"
            autoComplete="email"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          {error && <Aviso texto={error} />}
          <Boton type="submit" variante="primario" className="w-full" cargando={enviando} disabled={!email.trim()}>
            Enviar enlace
          </Boton>
          <Link to="/ingreso" className="block text-center text-sm text-texto-2 underline underline-offset-4">
            Volver a ingresar
          </Link>
        </form>
      )}
    </Hoja>
  );
}

/** Página del enlace del correo: elige la contraseña nueva. Cierra todas las sesiones abiertas. */
export function PaginaRestablecer() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [repetir, setRepetir] = useState("");
  const [listo, setListo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (password !== repetir) {
      setError("Las dos contraseñas no coinciden.");
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      await post("/auth/restablecer-contrasena", { token, password });
      setListo(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo restablecer la contraseña.");
    } finally {
      setEnviando(false);
    }
  }

  if (!token) {
    return (
      <Hoja titulo="Enlace incompleto">
        <p className="mt-3 text-texto-2">El enlace no trae el código. Pide uno nuevo.</p>
        <Link to="/olvide-contrasena" className="mt-4 inline-block text-sm font-medium text-primario-osc underline underline-offset-4">
          Pedir un enlace nuevo
        </Link>
      </Hoja>
    );
  }

  return (
    <Hoja titulo="Elige una contraseña nueva">
      {listo ? (
        <div role="status" className="mt-4 space-y-3 text-texto-2">
          <p className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-ok" aria-hidden />
            Listo. Cambiamos tu contraseña y cerramos las sesiones que tenías abiertas.
          </p>
          <Link to="/ingreso" className="inline-block">
            <Boton variante="primario">Ingresar</Boton>
          </Link>
        </div>
      ) : (
        <form onSubmit={enviar} className="mt-6 space-y-4" noValidate>
          <p className="text-sm text-texto-2">
            Al menos 10 caracteres. Evita contraseñas comunes, tu nombre o tu correo; una frase de varias palabras es fácil de recordar.
          </p>
          <Campo
            etiqueta="Contraseña nueva"
            icono={LockKeyhole}
            type="password"
            autoComplete="new-password"
            required
            minLength={10}
            autoFocus
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Campo
            etiqueta="Repítela"
            icono={LockKeyhole}
            type="password"
            autoComplete="new-password"
            required
            value={repetir}
            onChange={(e) => setRepetir(e.target.value)}
          />
          {error && <Aviso texto={error} />}
          <Boton type="submit" variante="primario" className="w-full" cargando={enviando} disabled={password.length < 10 || !repetir}>
            Guardar contraseña
          </Boton>
          {error && (
            <Link to="/olvide-contrasena" className="block text-center text-sm text-texto-2 underline underline-offset-4">
              Pedir un enlace nuevo
            </Link>
          )}
        </form>
      )}
    </Hoja>
  );
}

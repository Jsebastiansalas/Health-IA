import { AlertCircle, ArrowLeft, Check, Eye, EyeOff, LockKeyhole, Mail, UserRound } from "../iconos";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Marca } from "../componentes/Marca";
import { Boton } from "../componentes/ui/Boton";
import { Campo } from "../componentes/ui/Campo";
import { useSesion } from "../sesion";

/** Cuenta personal para pacientes y familias: un espacio propio, con borrado inmediato de los originales. */
export function PaginaRegistro() {
  const { registrarPersonal } = useSesion();
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [verClave, setVerClave] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await registrarPersonal(nombre.trim(), email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No fue posible crear la cuenta.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="grid min-h-[100svh] grid-cols-[minmax(0,1fr)] lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <section className="relative m-3 hidden flex-col justify-between rounded-lg bg-marino p-10 text-white lg:flex xl:p-16">
        <Link to="/" aria-label="MedTender, volver al inicio" className="w-fit">
          <Marca className="text-white" />
        </Link>
        <div className="max-w-lg">
          <h1 className="text-4xl font-semibold">Entiende los papeles que te dan en el hospital.</h1>
          <ul className="mt-8 space-y-4 text-base">
            {[
              "Sube tus resultados, historia clínica u órdenes, en PDF o con una foto.",
              "Pregunta qué dicen, con la cita exacta del documento.",
              "Consulta los efectos de un medicamento, con su fuente.",
              "Borras tu historial y tu cuenta cuando quieras.",
            ].map((t) => (
              <li key={t} className="flex gap-3">
                <Check className="mt-0.5 size-5 shrink-0" strokeWidth={2.5} aria-hidden />
                {t}
              </li>
            ))}
          </ul>
        </div>
        <span aria-hidden />
      </section>

      <section className="flex items-center justify-center px-4 py-10 sm:px-10">
        <div className="panel w-full max-w-md p-8 sm:p-10">
          <Link to="/" className="mb-8 inline-flex items-center gap-2 text-sm font-medium text-texto-3 transition-colors hover:text-primario lg:hidden">
            <ArrowLeft className="size-4" aria-hidden />
            Inicio
          </Link>
          <h2 className="text-2xl font-semibold leading-tight">Crea tu cuenta personal</h2>
          <p className="mt-2 text-sm text-texto-2">Para pacientes y familias. No necesitas una institución.</p>

          <form onSubmit={enviar} className="mt-8 space-y-4" noValidate>
            <Campo etiqueta="Tu nombre" icono={UserRound} autoComplete="name" required autoFocus minLength={2} maxLength={150}
              value={nombre} onChange={(e) => setNombre(e.target.value)} />
            <Campo etiqueta="Correo electrónico" icono={Mail} type="email" autoComplete="username" required
              value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nombre@correo.com" />
            <Campo
              etiqueta="Contraseña (mínimo 10 caracteres)"
              icono={LockKeyhole}
              type={verClave ? "text" : "password"}
              autoComplete="new-password"
              required
              minLength={10}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              extremo={
                <button
                  type="button"
                  onClick={() => setVerClave((v) => !v)}
                  className="grid size-8 place-items-center rounded-lg text-texto-3 transition-colors hover:bg-texto/8 hover:text-texto"
                  aria-label={verClave ? "Ocultar contraseña" : "Mostrar contraseña"}
                  aria-pressed={verClave}
                >
                  {verClave ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              }
            />
            {error && (
              <div role="alert" className="flex items-start gap-3 rounded-lg border border-peligro/40 bg-peligro/10 px-4 py-3 text-sm text-peligro">
                <AlertCircle className="mt-0.5 size-4 shrink-0 text-peligro" aria-hidden />
                {error}
              </div>
            )}
            <Boton type="submit" variante="primario" tamano="lg" className="w-full" cargando={enviando}>
              {enviando ? "Creando…" : "Crear cuenta"}
            </Boton>
          </form>
          <p className="mt-6 text-center text-sm text-texto-2">
            ¿Ya tienes cuenta?{" "}
            <Link to="/ingreso" className="font-semibold text-primario underline underline-offset-4">
              Ingresa
            </Link>
          </p>
        </div>
      </section>
    </div>
  );
}

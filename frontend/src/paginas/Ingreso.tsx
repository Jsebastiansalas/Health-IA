import { AlertCircle, ArrowLeft, Check, Eye, EyeOff, Key, LockKeyhole, Mail } from "../iconos";
import { motion, useReducedMotion } from "motion/react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Marca } from "../componentes/Marca";
import { Boton } from "../componentes/ui/Boton";
import { Campo } from "../componentes/ui/Campo";
import { useSesion } from "../sesion";

export function PaginaIngreso() {
  const { ingresar, verificarDosPasos } = useSesion();
  const [desafio, setDesafio] = useState<string | null>(null);
  const [codigo, setCodigo] = useState("");
  const quieto = useReducedMotion();
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
      if (desafio) {
        await verificarDosPasos(desafio, codigo);
      } else {
        const r = await ingresar(email, password);
        if (r.desafio) setDesafio(r.desafio);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "No fue posible ingresar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="grid min-h-[100svh] grid-cols-[minmax(0,1fr)] lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      {/* Lado de marca: la promesa del producto */}
      <section className="relative m-3 hidden flex-col justify-between rounded-lg bg-marino p-10 text-white lg:flex xl:p-16">
        <Link to="/" aria-label="MedTender, volver al inicio" className="w-fit">
          <Marca className="text-white" />
        </Link>
        <div className="max-w-lg">
          <h1 className="text-4xl font-semibold">Tus expedientes de salud, con la fuente a un clic.</h1>
          <ul className="mt-8 space-y-4 text-base">
            {[
              "Tus documentos de salud, explicados y con la cita al lado.",
              "Cada respuesta cita el documento, la página y el texto exacto.",
              "Si los documentos no la respaldan, te lo dice.",
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

      {/* Formulario */}
      <section className="relative flex items-center justify-center px-4 py-10 sm:px-10">
        <motion.div
          initial={quieto ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="panel relative w-full max-w-md p-8 sm:p-10"
        >
          <Link
            to="/"
            className="mb-8 inline-flex items-center gap-2 text-sm font-medium text-texto-3 transition-colors hover:text-primario lg:hidden"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Inicio
          </Link>
          <h2 className="relative text-2xl font-semibold leading-tight text-texto">
            {desafio ? "Verificación en dos pasos" : "Ingresa a tu cuenta"}
          </h2>
          <p className="relative mt-2 text-sm text-texto-2">
            {desafio
              ? "Escribe el código de 6 dígitos de tu app de autenticación, o uno de tus códigos de respaldo."
              : "Usa el correo con el que te registraste."}
          </p>

          {desafio ? (
            <form onSubmit={enviar} className="relative mt-8 space-y-4" noValidate>
              <Campo
                etiqueta="Código de verificación"
                icono={Key}
                inputMode="numeric"
                autoComplete="one-time-code"
                required
                autoFocus
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
                placeholder="123456"
              />
              {error && (
                <div role="alert" className="flex items-start gap-3 rounded-lg border border-peligro/40 bg-peligro/10 px-4 py-3 text-sm text-peligro">
                  <AlertCircle className="mt-0.5 size-4 shrink-0 text-peligro" aria-hidden />
                  {error}
                </div>
              )}
              <Boton type="submit" variante="primario" tamano="lg" className="w-full" cargando={enviando} disabled={!codigo.trim()}>
                {enviando ? "Verificando…" : "Verificar"}
              </Boton>
              <button
                type="button"
                className="w-full text-center text-sm text-texto-3 underline underline-offset-4 hover:text-texto"
                onClick={() => {
                  setDesafio(null);
                  setCodigo("");
                  setError(null);
                }}
              >
                Volver a escribir la contraseña
              </button>
            </form>
          ) : (
          <form onSubmit={enviar} className="relative mt-8 space-y-4" noValidate>
            <Campo
              etiqueta="Correo electrónico"
              icono={Mail}
              type="email"
              autoComplete="username"
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="nombre@institucion.co"
            />
            <Campo
              etiqueta="Contraseña"
              icono={LockKeyhole}
              type={verClave ? "text" : "password"}
              autoComplete="current-password"
              required
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
              {enviando ? "Verificando…" : "Ingresar"}
            </Boton>
            <p className="text-center text-sm">
              <Link to="/olvide-contrasena" className="text-texto-2 underline underline-offset-4 hover:text-texto">
                ¿Olvidaste tu contraseña?
              </Link>
            </p>
          </form>
          )}
          <p className="relative mt-6 text-center text-sm text-texto-2">
            ¿Eres paciente o familiar?{" "}
            <Link to="/registro" className="font-semibold text-primario underline underline-offset-4">
              Crea tu cuenta personal
            </Link>
          </p>
        </motion.div>
      </section>
    </div>
  );
}

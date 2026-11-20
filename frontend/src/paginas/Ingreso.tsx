import { AlertCircle, ArrowLeft, Check, Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Montanas } from "../arte/Montanas";
import { AvisoPurga } from "../arte/TarjetasUI";
import { Marca } from "../componentes/Marca";
import { Boton } from "../componentes/ui/Boton";
import { Campo } from "../componentes/ui/Campo";
import { useSesion } from "../sesion";

export function PaginaIngreso() {
  const { ingresar } = useSesion();
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
      await ingresar(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No fue posible ingresar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="relative isolate grid min-h-[100svh] overflow-hidden lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      {/* Lado de marca: el cielo de la bienvenida, con la promesa del producto */}
      <section className="relative isolate m-3 hidden flex-col justify-between overflow-hidden rounded-xl p-10 text-tx lg:flex xl:p-14">
        <Montanas />
        <Link to="/" aria-label="MedTender, volver al inicio" className="relative w-fit">
          <Marca />
        </Link>
        <div className="relative max-w-lg">
          <h1 className="text-[clamp(2.2rem,3.2vw,3.2rem)]">
            Tu expediente, con la fuente a un clic.
          </h1>
          <ul className="mt-8 space-y-3.5 text-[1.02rem] text-tx">
            {[
              "Respuestas con extracto literal, página y huella del archivo.",
              "El PDF se elimina del servidor tras indexarlo.",
              "Lo abres desde tu equipo, sin subirlo de nuevo.",
            ].map((t) => (
              <li key={t} className="flex gap-3">
                <Check className="mt-0.5 size-5 shrink-0" strokeWidth={2.5} aria-hidden />
                {t}
              </li>
            ))}
          </ul>
          <AvisoPurga className="mt-10" />
        </div>
        <span aria-hidden />
      </section>

      {/* Formulario */}
      <section className="relative flex items-center justify-center px-5 py-10 sm:px-10">
        <motion.div
          initial={quieto ? false : { opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="relative w-full max-w-md rounded-xl bg-panel p-8 sm:p-10"
        >
          <Link
            to="/"
            className="mb-7 inline-flex items-center gap-1.5 text-sm font-medium text-tx-3 transition-colors hover:text-hema lg:hidden"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Inicio
          </Link>
          <h2 className="relative font-display text-[1.7rem] font-[480] leading-tight text-tx [font-stretch:112%]">Ingresa a tu cuenta</h2>
          <p className="relative mt-2 text-[0.95rem] text-tx-2">Usa el correo con el que tu organización te registró.</p>

          <form onSubmit={enviar} className="relative mt-8 space-y-5" noValidate>
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
                  className="grid size-8 place-items-center rounded-lg text-tx-3 transition-colors hover:bg-ink/8 hover:text-ink"
                  aria-label={verClave ? "Ocultar contraseña" : "Mostrar contraseña"}
                  aria-pressed={verClave}
                >
                  {verClave ? <EyeOff className="size-[1.05rem]" /> : <Eye className="size-[1.05rem]" />}
                </button>
              }
            />
            {error && (
              <div role="alert" className="flex items-start gap-2.5 rounded-lg border border-coral/40 bg-coral/10 px-3.5 py-3 text-sm text-coral">
                <AlertCircle className="mt-0.5 size-4 shrink-0 text-coral" aria-hidden />
                {error}
              </div>
            )}
            <Boton type="submit" variante="primario" tamano="lg" className="w-full" cargando={enviando}>
              {enviando ? "Verificando…" : "Ingresar"}
            </Boton>
          </form>
        </motion.div>
      </section>
    </div>
  );
}

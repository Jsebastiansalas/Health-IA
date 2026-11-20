import { AlertCircle, ArrowLeft, Check, Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Pinza, PlacaPliego } from "../arte/Placa";
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
      {/* Lado de marca: el negatoscopio con la promesa escrita a mano sobre la placa */}
      <section className="panel-luz relative hidden flex-col justify-between overflow-hidden p-12 text-[#0a1322] lg:flex xl:p-16">
        <Link to="/" aria-label="MedTender, volver al inicio" className="relative w-fit rounded-lg bg-[#0a1322] px-3 py-2">
          <Marca />
        </Link>
        <div className="relative my-10 flex items-center gap-10 xl:gap-14">
          <div className="relative w-52 shrink-0 pt-3 xl:w-60">
            <Pinza className="left-[18%] !h-6 !w-12" />
            <Pinza className="right-[18%] !h-6 !w-12" />
            <div className="aspect-[4/5] overflow-hidden rounded-[3px] shadow-[0_22px_26px_-16px_rgb(10_19_34/0.75)]">
              <PlacaPliego modo="hallazgo" />
            </div>
          </div>
          <div className="max-w-md">
            <h1 className="text-[clamp(2.3rem,3.4vw,3.5rem)] font-extrabold leading-[1] text-[#0a1322]">
              Tu expediente, con la fuente a un clic.
            </h1>
            <ul className="mt-7 space-y-3.5 text-[1.02rem] text-[#243447]">
              {[
                "Respuestas con extracto literal, página y huella del archivo.",
                "El PDF se elimina del servidor tras indexarlo.",
                "Lo abres desde tu equipo, sin subirlo de nuevo.",
              ].map((t) => (
                <li key={t} className="flex gap-3">
                  <Check className="mt-0.5 size-5 shrink-0 text-[#0a1322]" strokeWidth={3} aria-hidden />
                  {t}
                </li>
              ))}
            </ul>
          </div>
        </div>
        <p className="rotulo relative font-semibold text-[#2f4a5e]">Datos de la placa de ejemplo</p>
      </section>

      {/* Formulario */}
      <section className="relative flex items-center justify-center px-5 py-10 sm:px-10">
        <motion.div
          initial={quieto ? false : { opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="vidrio-solido relative w-full max-w-md overflow-hidden rounded-xl p-7 sm:p-9"
        >
          <Link
            to="/"
            className="mb-7 inline-flex items-center gap-1.5 text-sm font-medium text-tx-3 transition-colors hover:text-hema lg:hidden"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Inicio
          </Link>
          <h2 className="relative font-display text-[1.9rem] font-extrabold leading-tight text-tx">Ingresa a tu cuenta</h2>
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

import { AlertCircle, ArrowLeft, Eye, EyeOff, LockKeyhole, Mail, ShieldCheck } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { BarraEscala, Escudo } from "../arte/Decoracion";
import { Tejido } from "../arte/Tejido";
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
      {/* Lado de marca: un campo de tejido a sangre, con el titular encima */}
      <section className="relative hidden flex-col justify-between overflow-hidden bg-hema-pro p-12 text-white lg:flex xl:p-16">
        <div className="absolute inset-0 -z-0 opacity-90" aria-hidden>
          <Tejido semilla={13} celula={64} tinte={0.95} lavanda={0.5} />
          <div className="absolute inset-0 bg-[linear-gradient(160deg,rgb(28_23_82/0.88)_20%,rgb(28_23_82/0.55)_60%,rgb(28_23_82/0.2)_100%)]" />
        </div>
        <Link to="/" aria-label="MedTender, volver al inicio" className="relative">
          <Marca oscuro />
        </Link>
        <div className="relative max-w-lg">
          <h1 className="text-[clamp(2.4rem,3.6vw,3.7rem)] font-bold leading-[1.02]">Tu expediente, con la fuente a un clic.</h1>
          <ul className="mt-8 space-y-4 text-[1.02rem] text-white/85">
            {[
              "Respuestas con extracto literal, página y huella del archivo.",
              "El PDF se elimina del servidor tras indexarlo.",
              "Lo abres desde tu equipo, sin subirlo de nuevo.",
            ].map((t) => (
              <li key={t} className="flex gap-3">
                <ShieldCheck className="mt-0.5 size-5 shrink-0 text-eosina-clara" aria-hidden />
                {t}
              </li>
            ))}
          </ul>
        </div>
        <BarraEscala micras={50} className="relative !text-white" />
      </section>

      {/* Formulario */}
      <section className="relative flex items-center justify-center px-5 py-10 sm:px-10">
        <div className="absolute inset-0 -z-10 lg:hidden" aria-hidden>
          <Tejido semilla={13} celula={60} tinte={0.35} lavanda={0.5} />
          <div className="absolute inset-0 bg-lila-50/70" />
        </div>
        <motion.div
          initial={quieto ? false : { opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="vidrio-solido relative w-full max-w-md overflow-hidden rounded-[1.75rem] p-7 sm:p-9"
        >
          <Link
            to="/"
            className="mb-7 inline-flex items-center gap-1.5 text-sm font-medium text-tx-3 transition-colors hover:text-hema-osc lg:hidden"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Inicio
          </Link>
          <Escudo className="absolute -right-8 -top-6 w-36 opacity-20" />
          <h2 className="relative font-display text-[1.9rem] font-bold leading-tight text-ink">Ingresa a tu cuenta</h2>
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
              <div role="alert" className="flex items-start gap-2.5 rounded-xl border border-coral/35 bg-coral/8 px-3.5 py-3 text-sm text-[#b3202f]">
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

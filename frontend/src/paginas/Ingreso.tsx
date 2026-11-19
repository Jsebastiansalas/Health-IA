import { useState, type FormEvent } from "react";
import { Marca } from "../componentes/Marco";
import { useSesion } from "../sesion";

export function PaginaIngreso() {
  const { ingresar } = useSesion();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
    <div className="grid min-h-screen lg:grid-cols-[1.15fr_1fr]">
      <section className="relative flex flex-col justify-between overflow-hidden border-r border-papel-3 bg-tinta px-10 py-12 text-papel lg:px-16">
        <Marca grande />
        <div className="relative z-10 max-w-xl animate-aparecer">
          <p className="etiqueta mb-6 !text-papel-3">Licitaciones y auditoría en salud</p>
          <h1 className="font-display text-5xl leading-[1.05] font-light lg:text-6xl">
            Interrogue el expediente completo, <em className="text-[#e9a19c]">aunque el PC de la oficina esté apagado.</em>
          </h1>
          <p className="mt-8 max-w-md text-papel-3">
            Los PDF originales se quedan en su computador. El servidor conserva solo fragmentos, vectores y la
            trazabilidad; la copia temporal se destruye en cuanto se verifica la indexación.
          </p>
        </div>
        <div className="relative z-10 flex flex-wrap gap-3 text-xs">
          {["Pliegos", "Adendas", "Fichas técnicas", "Registros INVIMA", "Cuadros de precios"].map((t) => (
            <span key={t} className="rounded-sm border border-papel/25 px-2 py-1 font-mono tracking-wider text-papel-3">
              {t}
            </span>
          ))}
        </div>
        {/* Sello decorativo */}
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 -bottom-24 grid size-[26rem] place-items-center rounded-full border-[3px] border-sello/50 font-mono text-sm tracking-[0.5em] text-sello/60"
          style={{ transform: "rotate(-14deg)" }}
        >
          <div className="grid size-[21rem] place-items-center rounded-full border border-sello/40">
            PDF · ELIMINADO · DEL · SERVIDOR
          </div>
        </div>
      </section>

      <section className="flex items-center justify-center px-8 py-16">
        <form onSubmit={enviar} className="w-full max-w-sm animate-aparecer space-y-8">
          <div>
            <p className="etiqueta">Acceso restringido</p>
            <h2 className="mt-2 font-display text-3xl">Ingresar al archivo</h2>
          </div>
          <label className="block">
            <span className="etiqueta">Correo institucional</span>
            <input className="campo" type="email" autoComplete="username" required value={email}
              onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="block">
            <span className="etiqueta">Contraseña</span>
            <input className="campo" type="password" autoComplete="current-password" required value={password}
              onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error && (
            <p role="alert" className="border-l-2 border-sello bg-sello-claro px-3 py-2 text-sm text-sello">
              {error}
            </p>
          )}
          <button className="boton boton-tinta w-full py-3" disabled={enviando}>
            {enviando ? "Verificando…" : "Ingresar"}
          </button>
        </form>
      </section>
    </div>
  );
}

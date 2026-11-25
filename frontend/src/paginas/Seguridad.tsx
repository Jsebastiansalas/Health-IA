import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import QRCode from "qrcode";
import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { api, post } from "../api/cliente";
import type { Tokens } from "../api/tipos";
import { Boton } from "../componentes/ui/Boton";
import { Campo } from "../componentes/ui/Campo";
import { Insignia } from "../componentes/ui/Insignia";
import { Check, Copy, Key, LockKeyhole, LogOut, QrCode, ShieldCheck } from "../iconos";
import { useSesion } from "../sesion";

interface EstadoDosPasos {
  activo: boolean;
  respaldos_disponibles: number;
}

function Seccion({ id, titulo, icono: Icono, children }: { id: string; titulo: string; icono: typeof Key; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="panel p-6">
      <h2 id={id} className="flex items-center gap-2 text-xl font-semibold">
        <Icono className="size-5 text-primario" aria-hidden />
        {titulo}
      </h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

const mensaje = (e: unknown) => (e instanceof Error ? e.message : "No se pudo completar");

/** Seguridad de la cuenta: contraseña, verificación en dos pasos y sesiones abiertas. */
export function PaginaSeguridad() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header>
        <h1 className="flex items-center gap-3 text-3xl font-semibold">
          <ShieldCheck className="size-7 text-primario" aria-hidden />
          Seguridad de la cuenta
        </h1>
        <p className="mt-2 text-texto-2">Cada cambio te llega por correo para que sepas si alguien más lo hizo.</p>
      </header>
      <DosPasos />
      <CambiarContrasena />
      <CerrarSesiones />
    </div>
  );
}

function CambiarContrasena() {
  const { renovarTokens } = useSesion();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const cambiar = useMutation({
    mutationFn: () => post<Tokens>("/auth/cambiar-contrasena", { actual, nueva }),
    onSuccess: (t) => {
      renovarTokens(t);
      setActual("");
      setNueva("");
      toast.success("Contraseña cambiada", { description: "Cerramos tus sesiones en otros dispositivos." });
    },
  });
  return (
    <Seccion id="sec-clave" titulo="Contraseña" icono={LockKeyhole}>
      <form
        className="space-y-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          cambiar.mutate();
        }}
      >
        <Campo etiqueta="Contraseña actual" type="password" autoComplete="current-password" value={actual} onChange={(e) => setActual(e.target.value)} />
        <Campo
          etiqueta="Contraseña nueva"
          type="password"
          autoComplete="new-password"
          minLength={10}
          value={nueva}
          onChange={(e) => setNueva(e.target.value)}
        />
        <p className="text-xs text-texto-3">Al menos 10 caracteres; no uses contraseñas comunes, tu nombre ni tu correo.</p>
        {cambiar.error && (
          <p role="alert" className="text-sm text-peligro">
            {mensaje(cambiar.error)}
          </p>
        )}
        <Boton type="submit" variante="primario" cargando={cambiar.isPending} disabled={!actual || nueva.length < 10}>
          Cambiar contraseña
        </Boton>
      </form>
    </Seccion>
  );
}

function CerrarSesiones() {
  const { renovarTokens } = useSesion();
  const cerrar = useMutation({
    mutationFn: () => post<Tokens>("/auth/cerrar-sesiones", {}),
    onSuccess: (t) => {
      renovarTokens(t);
      toast.success("Cerramos tus sesiones en los demás dispositivos");
    },
    onError: (e) => toast.error(mensaje(e)),
  });
  return (
    <Seccion id="sec-sesiones" titulo="Sesiones abiertas" icono={LogOut}>
      <p className="text-sm text-texto-2">
        Si ingresaste desde un computador ajeno o perdiste el teléfono, cierra todas las sesiones. Esta queda abierta.
      </p>
      <Boton className="mt-4" variante="secundario" cargando={cerrar.isPending} onClick={() => cerrar.mutate()}>
        Cerrar las demás sesiones
      </Boton>
    </Seccion>
  );
}

function DosPasos() {
  const cliente = useQueryClient();
  const { data: estado } = useQuery({ queryKey: ["dos-pasos"], queryFn: () => api<EstadoDosPasos>("/auth/2fa") });
  const [inicio, setInicio] = useState<{ secreto: string; uri: string } | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [codigo, setCodigo] = useState("");
  const [respaldos, setRespaldos] = useState<string[] | null>(null);
  const [desactivando, setDesactivando] = useState(false);
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (!inicio) return setQr(null);
    // El QR se dibuja aquí mismo: el secreto no pasa por ningún servicio externo.
    void QRCode.toDataURL(inicio.uri, { margin: 1, width: 220, errorCorrectionLevel: "M" }).then(setQr);
  }, [inicio]);

  const refrescar = () => {
    void cliente.invalidateQueries({ queryKey: ["dos-pasos"] });
    void cliente.invalidateQueries({ queryKey: ["yo"] });
  };
  const iniciar = useMutation({ mutationFn: () => post<{ secreto: string; uri: string }>("/auth/2fa/iniciar", {}), onSuccess: setInicio });
  const activar = useMutation({
    mutationFn: () => post<{ codigos_respaldo: string[] }>("/auth/2fa/activar", { codigo }),
    onSuccess: (r) => {
      setRespaldos(r.codigos_respaldo);
      setInicio(null);
      setCodigo("");
      refrescar();
    },
  });
  const desactivar = useMutation({
    mutationFn: () => post("/auth/2fa/desactivar", { password, codigo }),
    onSuccess: () => {
      setDesactivando(false);
      setPassword("");
      setCodigo("");
      refrescar();
      toast.success("Verificación en dos pasos desactivada");
    },
  });

  async function copiar() {
    try {
      await navigator.clipboard.writeText((respaldos ?? []).join("\n"));
      toast.success("Códigos copiados");
    } catch {
      toast.error("No se pudieron copiar");
    }
  }

  return (
    <Seccion id="sec-2fa" titulo="Verificación en dos pasos" icono={Key}>
      {respaldos ? (
        <div className="space-y-3">
          <p className="flex items-center gap-2 font-medium text-ok">
            <Check className="size-5" aria-hidden />
            Quedó activada.
          </p>
          <p className="text-sm text-texto-2">
            Guarda estos códigos de respaldo en un lugar seguro: cada uno sirve una vez si pierdes el teléfono. No los volveremos a mostrar.
          </p>
          <ul className="grid grid-cols-2 gap-2 rounded-lg bg-panel-2 p-4 font-mono text-sm sm:grid-cols-5">
            {respaldos.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <div className="flex gap-2">
            <Boton variante="secundario" onClick={() => void copiar()}>
              <Copy className="size-4" aria-hidden />
              Copiar
            </Boton>
            <Boton variante="fantasma" onClick={() => setRespaldos(null)}>
              Ya los guardé
            </Boton>
          </div>
        </div>
      ) : estado?.activo ? (
        <div className="space-y-3">
          <p className="flex flex-wrap items-center gap-2">
            <Insignia tono="ok">
              <ShieldCheck className="size-4" aria-hidden />
              Activa
            </Insignia>
            <span className="text-sm text-texto-2">Te quedan {estado.respaldos_disponibles} códigos de respaldo.</span>
          </p>
          {desactivando ? (
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                desactivar.mutate();
              }}
            >
              <Campo etiqueta="Contraseña" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
              <Campo etiqueta="Código de la app o de respaldo" inputMode="numeric" autoComplete="one-time-code" value={codigo} onChange={(e) => setCodigo(e.target.value)} />
              {desactivar.error && (
                <p role="alert" className="text-sm text-peligro">
                  {mensaje(desactivar.error)}
                </p>
              )}
              <div className="flex gap-2">
                <Boton type="submit" variante="primario" cargando={desactivar.isPending} disabled={!password || !codigo}>
                  Desactivar
                </Boton>
                <Boton type="button" variante="fantasma" onClick={() => setDesactivando(false)}>
                  Cancelar
                </Boton>
              </div>
            </form>
          ) : (
            <Boton variante="fantasma" onClick={() => setDesactivando(true)}>
              Desactivar
            </Boton>
          )}
        </div>
      ) : inicio ? (
        <div className="space-y-4">
          <ol className="list-decimal space-y-1 pl-5 text-sm text-texto-2">
            <li>Abre tu app de autenticación (Google Authenticator, Microsoft Authenticator, 1Password…).</li>
            <li>Escanea este código o escribe la clave.</li>
            <li>Escribe el código de 6 dígitos que muestra la app.</li>
          </ol>
          <div className="flex flex-wrap items-center gap-6">
            {qr ? (
              <img src={qr} alt="Código QR para tu app de autenticación" width={220} height={220} className="rounded-lg border border-borde bg-white p-2" />
            ) : (
              <div className="grid size-[220px] place-items-center rounded-lg bg-panel-2">
                <QrCode className="size-10 text-texto-3" aria-hidden />
              </div>
            )}
            <p className="text-sm text-texto-2">
              Clave para escribirla a mano:
              <span className="mt-1 block break-all font-mono text-texto">{inicio.secreto.replace(/(.{4})/g, "$1 ").trim()}</span>
            </p>
          </div>
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              activar.mutate();
            }}
          >
            <Campo etiqueta="Código de la app" inputMode="numeric" autoComplete="one-time-code" value={codigo} onChange={(e) => setCodigo(e.target.value)} />
            <Boton type="submit" variante="primario" cargando={activar.isPending} disabled={codigo.replace(/\s/g, "").length !== 6}>
              Activar
            </Boton>
          </form>
          {activar.error && (
            <p role="alert" className="text-sm text-peligro">
              {mensaje(activar.error)}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-texto-2">
            Además de tu contraseña, te pediremos un código de una app de tu teléfono. Si alguien descubre tu contraseña, no podrá entrar.
          </p>
          <Boton variante="primario" cargando={iniciar.isPending} onClick={() => iniciar.mutate()}>
            Activar verificación en dos pasos
          </Boton>
          {iniciar.error && (
            <p role="alert" className="text-sm text-peligro">
              {mensaje(iniciar.error)}
            </p>
          )}
        </div>
      )}
    </Seccion>
  );
}

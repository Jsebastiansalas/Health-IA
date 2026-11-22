import { useQuery } from "@tanstack/react-query";
import * as Tabs from "@radix-ui/react-tabs";
import { AlertTriangle, ArrowLeft, ChevronRight, FileStack, MessagesSquare, UserRound } from "lucide-react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/cliente";
import type { Cita, Documento, Expediente } from "../api/tipos";
import { ConsolaRag } from "../componentes/ConsolaRag";
import { Consentimiento } from "../componentes/Consentimiento";
import { PanelDocumentos } from "../componentes/PanelDocumentos";
import { BotonBorrarHistorial } from "../componentes/Privacidad";
import { boton } from "../componentes/ui/Boton";
import { Esqueleto } from "../componentes/ui/Esqueleto";
import { Insignia } from "../componentes/ui/Insignia";
import { cn } from "../lib/cn";
import { useConsentimiento } from "../lib/consentimiento";
import { esConsultable, TIPOS_EXPEDIENTE } from "../lib/formato";
import { useMediaQuery } from "../lib/useMediaQuery";

// PDF.js (~1,3 MB con su worker) solo se descarga cuando se abre una cita.
const VisorLocal = lazy(() => import("../componentes/VisorLocal").then((m) => ({ default: m.VisorLocal })));

const PERMISO: Record<string, string> = { ADMIN: "Administras", EDITOR: "Editas", LECTOR: "Consultas" };

function Cifra({ valor, etiqueta }: { valor: string | number; etiqueta: string }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <dd className="num text-[1.05rem] font-semibold">{valor}</dd>
      <dt className="text-[0.82rem] text-tinta-3">{etiqueta}</dt>
    </div>
  );
}

export function PaginaExpediente() {
  const { id = "" } = useParams();
  const [citaAbierta, setCitaAbierta] = useState<Cita | null>(null);
  const [pestana, setPestana] = useState("folios");
  // Las cuentas personales deben aceptar el consentimiento antes de subir documentos o consultar.
  const consentimiento = useConsentimiento();
  // Con ancho de sobra, el original se abre junto a la consulta; si no, como ventana encima.
  const ancha = useMediaQuery("(min-width: 1280px)");
  const { data: expediente, error } = useQuery({
    queryKey: ["expediente", id],
    queryFn: () => api<Expediente>(`/expedientes/${id}`),
  });
  const { data: documentos } = useQuery({
    queryKey: ["documentos", id],
    queryFn: () => api<Documento[]>(`/expedientes/${id}/documentos`),
  });
  // En pantallas con pestañas, quien ya tiene documentos indexados viene a consultar: se abre en «Consulta».
  const pestanaElegida = useRef(false);
  useEffect(() => {
    if (pestanaElegida.current || !documentos) return;
    pestanaElegida.current = true;
    if (documentos.some((d) => esConsultable(d.estado_indexacion))) setPestana("consulta");
  }, [documentos]);

  if (error) {
    return (
      <div role="alert" className="folio flex max-w-xl items-start gap-4 p-7">
        <AlertTriangle className="mt-1 size-6 shrink-0 text-peligro" aria-hidden />
        <div>
          <h1 className="text-2xl font-semibold">Expediente no disponible</h1>
          <p className="mt-2 text-tinta-2">{(error as Error).message}</p>
          <Link to="/" className={boton({ tamano: "md" }) + " mt-5"}>
            <ArrowLeft className="size-4" aria-hidden />
            Volver a expedientes
          </Link>
        </div>
      </div>
    );
  }
  if (!expediente) {
    return (
      <div aria-busy aria-label="Abriendo expediente">
        <Esqueleto className="mb-4 h-5 w-48" />
        <Esqueleto className="h-44 rounded-2xl" />
        <div className="mt-8 grid gap-6 xl:grid-cols-[minmax(300px,360px)_minmax(0,1fr)]">
          <Esqueleto className="h-96 rounded-2xl" />
          <Esqueleto className="h-96 rounded-2xl" />
        </div>
      </div>
    );
  }

  const acoplada = ancha && citaAbierta !== null;
  const puedeSubir = expediente.mi_permiso === "ADMIN" || expediente.mi_permiso === "EDITOR";
  const hayIndice = (documentos ?? []).some((d) => esConsultable(d.estado_indexacion));
  const indexados = (documentos ?? []).filter((d) => esConsultable(d.estado_indexacion));
  const fragmentos = indexados.reduce((suma, d) => suma + (d.total_chunks_guardados ?? 0), 0);

  return (
    <div className="animate-aparecer">
      <nav aria-label="Ruta" className="mb-5 flex items-center gap-1.5 text-sm text-tinta-3">
        <Link to="/" className="rounded-md transition-colors hover:text-accion">
          Expedientes
        </Link>
        <ChevronRight className="size-4" aria-hidden />
        <span className="font-mono text-tinta-2">{expediente.codigo_expediente}</span>
      </nav>

      <header className="mb-7 border-b border-tinta/15 pb-6">
        <div className="flex flex-wrap items-center gap-2">
          <Insignia tono={expediente.estado === "ABIERTO" ? "accion" : "neutro"}>{expediente.estado}</Insignia>
          <Insignia>
            <UserRound className="size-3.5" aria-hidden />
            {expediente.mi_permiso ? PERMISO[expediente.mi_permiso] : "Sin permiso"}
          </Insignia>
        </div>
        <h1 className="mt-3 max-w-4xl text-3xl font-semibold leading-[1.1] sm:text-4xl">{expediente.titulo}</h1>
        <p className="mt-2 text-tinta-2">
          <span className="font-mono text-tinta">{expediente.codigo_expediente}</span> ·{" "}
          {expediente.entidad_contratante ?? "Entidad no registrada"} · {TIPOS_EXPEDIENTE[expediente.tipo_expediente]}
        </p>
        <dl className="mt-4 flex flex-wrap gap-x-7 gap-y-2" aria-label="Resumen del expediente">
          <Cifra valor={documentos?.length ?? "—"} etiqueta="documentos" />
          <Cifra valor={documentos ? indexados.length : "—"} etiqueta="indexados (PDF eliminado)" />
          <Cifra valor={documentos ? fragmentos.toLocaleString("es-CO") : "—"} etiqueta="fragmentos consultables" />
          <Cifra valor={expediente.embedding_model_activo} etiqueta="modelo del índice" />
        </dl>
        {expediente.mi_permiso === "ADMIN" && (
          <div className="mt-4 -ml-3">
            <BotonBorrarHistorial expedienteId={id} />
          </div>
        )}
      </header>

      {consentimiento.pendiente && consentimiento.estado && (
        <Consentimiento
          version={consentimiento.estado.version}
          aceptando={consentimiento.aceptar.isPending}
          error={consentimiento.aceptar.error ? (consentimiento.aceptar.error as Error).message : undefined}
          alAceptar={() => consentimiento.aceptar.mutate()}
        />
      )}

      <Tabs.Root value={pestana} onValueChange={setPestana}>
        <Tabs.List className="folio mb-5 grid grid-cols-2 gap-1 rounded-md p-1 xl:hidden" aria-label="Secciones del expediente">
          {[
            ["folios", "Documentos", FileStack],
            ["consulta", "Consulta", MessagesSquare],
          ].map(([valor, texto, Icono]) => {
            const I = Icono as typeof FileStack;
            return (
              <Tabs.Trigger
                key={valor as string}
                value={valor as string}
                className="flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold text-tinta-2 transition-colors data-[state=active]:bg-accion/14 data-[state=active]:text-accion"
              >
                <I className="size-4" aria-hidden />
                {texto as string}
              </Tabs.Trigger>
            );
          })}
        </Tabs.List>

        <div className={cn("grid gap-8", acoplada ? "xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]" : "xl:grid-cols-[minmax(300px,360px)_minmax(0,1fr)]")}>
          <Tabs.Content value="folios" forceMount className={cn("data-[state=inactive]:hidden xl:sticky xl:top-6 xl:!block xl:max-h-[calc(100vh-3rem)] xl:self-start xl:overflow-y-auto xl:pr-1", acoplada && "xl:!hidden")}>
            <PanelDocumentos expedienteId={id} puedeSubir={puedeSubir && expediente.estado === "ABIERTO" && !consentimiento.pendiente} />
          </Tabs.Content>
          <Tabs.Content value="consulta" forceMount className="data-[state=inactive]:hidden xl:!block">
            <ConsolaRag expedienteId={id} hayIndice={hayIndice} alAbrirCita={setCitaAbierta} bloqueado={consentimiento.pendiente} />
          </Tabs.Content>
          {acoplada && citaAbierta && (
            <aside className="sticky top-6 hidden h-[calc(100vh-3rem)] xl:block">
              <Suspense fallback={<div className="folio grid h-full place-items-center text-tinta-2">Abriendo visor…</div>}>
                <VisorLocal cita={citaAbierta} alCerrar={() => setCitaAbierta(null)} acoplado />
              </Suspense>
            </aside>
          )}
        </div>
      </Tabs.Root>

      {/* Portal: la página tiene una animación con transform, que convertiría el `fixed` del
          visor en relativo a ese contenedor. */}
      {citaAbierta && !acoplada &&
        createPortal(
          <Suspense
            fallback={
              <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 text-white">
                Abriendo visor…
              </div>
            }
          >
            <VisorLocal cita={citaAbierta} alCerrar={() => setCitaAbierta(null)} />
          </Suspense>,
          document.body,
        )}
    </div>
  );
}

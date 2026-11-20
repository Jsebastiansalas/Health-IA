import { useQuery } from "@tanstack/react-query";
import * as Tabs from "@radix-ui/react-tabs";
import { AlertTriangle, ArrowLeft, ChevronRight, Cpu, FileStack, Layers, MessagesSquare, ShieldCheck, UserRound } from "lucide-react";
import { lazy, Suspense, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/cliente";
import type { Cita, Documento, Expediente } from "../api/tipos";
import { PlacaVacia } from "../arte/Placa";
import { ConsolaRag } from "../componentes/ConsolaRag";
import { PanelDocumentos } from "../componentes/PanelDocumentos";
import { boton } from "../componentes/ui/Boton";
import { Esqueleto } from "../componentes/ui/Esqueleto";
import { Insignia } from "../componentes/ui/Insignia";
import { esConsultable, TIPOS_EXPEDIENTE } from "../lib/formato";

// PDF.js (~1,3 MB con su worker) solo se descarga cuando se abre una cita.
const VisorLocal = lazy(() => import("../componentes/VisorLocal").then((m) => ({ default: m.VisorLocal })));

const PERMISO: Record<string, string> = { ADMIN: "Administras", EDITOR: "Editas", LECTOR: "Consultas" };

function Dato({ icono: Icono, etiqueta, valor }: { icono: typeof Cpu; etiqueta: string; valor: string | number }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-ink/10 bg-sala px-4 py-3">
      <Icono className="size-5 shrink-0 text-hema" strokeWidth={1.6} aria-hidden />
      <div className="min-w-0 leading-tight">
        <p className="num truncate text-[1.05rem] font-semibold">{valor}</p>
        <p className="truncate text-[0.74rem] text-tx-3">{etiqueta}</p>
      </div>
    </div>
  );
}

export function PaginaExpediente() {
  const { id = "" } = useParams();
  const [citaAbierta, setCitaAbierta] = useState<Cita | null>(null);
  const [pestana, setPestana] = useState("folios");
  const { data: expediente, error } = useQuery({
    queryKey: ["expediente", id],
    queryFn: () => api<Expediente>(`/expedientes/${id}`),
  });
  const { data: documentos } = useQuery({
    queryKey: ["documentos", id],
    queryFn: () => api<Documento[]>(`/expedientes/${id}/documentos`),
  });

  if (error) {
    return (
      <div role="alert" className="vidrio flex max-w-xl items-start gap-4 rounded-2xl p-7">
        <AlertTriangle className="mt-1 size-6 shrink-0 text-coral" aria-hidden />
        <div>
          <h1 className="text-2xl font-semibold">Expediente no disponible</h1>
          <p className="mt-2 text-tx-2">{(error as Error).message}</p>
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
        <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(320px,440px)_1fr]">
          <Esqueleto className="h-96 rounded-2xl" />
          <Esqueleto className="h-96 rounded-2xl" />
        </div>
      </div>
    );
  }

  const puedeSubir = expediente.mi_permiso === "ADMIN" || expediente.mi_permiso === "EDITOR";
  const hayIndice = (documentos ?? []).some((d) => esConsultable(d.estado_indexacion));
  const indexados = (documentos ?? []).filter((d) => esConsultable(d.estado_indexacion));
  const fragmentos = indexados.reduce((suma, d) => suma + (d.total_chunks_guardados ?? 0), 0);

  return (
    <div className="animate-aparecer">
      <nav aria-label="Ruta" className="mb-5 flex items-center gap-1.5 text-sm text-tx-3">
        <Link to="/" className="rounded-md transition-colors hover:text-hema">
          Expedientes
        </Link>
        <ChevronRight className="size-4" aria-hidden />
        <span className="font-mono text-tx-2">{expediente.codigo_expediente}</span>
      </nav>

      <header className="vidrio relative mb-8 overflow-hidden rounded-2xl p-6 sm:p-8">
        <PlacaVacia className="absolute -top-4 right-6 hidden w-28 rotate-6 opacity-70 md:block" />
        <div className="relative flex flex-wrap items-center gap-2">
          <Insignia tono={expediente.estado === "ABIERTO" ? "hema" : "neutro"}>{expediente.estado}</Insignia>
          <Insignia tono="hema">
            <UserRound className="size-3.5" aria-hidden />
            {expediente.mi_permiso ? PERMISO[expediente.mi_permiso] : "Sin permiso"}
          </Insignia>
        </div>
        <h1 className="relative mt-4 max-w-4xl text-3xl font-semibold leading-[1.08] sm:text-[2.6rem]">
          {expediente.titulo}
        </h1>
        <p className="relative mt-2 text-tx-2">
          <span className="font-mono text-hema">{expediente.codigo_expediente}</span> ·{" "}
          {expediente.entidad_contratante ?? "Entidad no registrada"} · {TIPOS_EXPEDIENTE[expediente.tipo_expediente]}
        </p>
        <div className="relative mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Dato icono={FileStack} etiqueta="documentos cargados" valor={documentos?.length ?? "—"} />
          <Dato icono={ShieldCheck} etiqueta="indexados, PDF eliminado" valor={documentos ? indexados.length : "—"} />
          <Dato icono={Layers} etiqueta="fragmentos consultables" valor={documentos ? fragmentos.toLocaleString("es-CO") : "—"} />
          <Dato icono={Cpu} etiqueta="modelo del índice" valor={expediente.embedding_model_activo} />
        </div>
      </header>

      <Tabs.Root value={pestana} onValueChange={setPestana}>
        <Tabs.List className="vidrio-solido mb-5 grid grid-cols-2 gap-1 rounded-2xl p-1 lg:hidden" aria-label="Secciones del expediente">
          {[
            ["folios", "Documentos", FileStack],
            ["consulta", "Consulta", MessagesSquare],
          ].map(([valor, texto, Icono]) => {
            const I = Icono as typeof FileStack;
            return (
              <Tabs.Trigger
                key={valor as string}
                value={valor as string}
                className="flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold text-tx-2 transition-colors data-[state=active]:bg-hema/14 data-[state=active]:text-hema"
              >
                <I className="size-4" aria-hidden />
                {texto as string}
              </Tabs.Trigger>
            );
          })}
        </Tabs.List>

        <div className="grid gap-8 lg:grid-cols-[minmax(340px,460px)_minmax(0,1fr)]">
          <Tabs.Content value="folios" forceMount className="data-[state=inactive]:hidden lg:!block">
            <PanelDocumentos expedienteId={id} puedeSubir={puedeSubir && expediente.estado === "ABIERTO"} />
          </Tabs.Content>
          <Tabs.Content value="consulta" forceMount className="data-[state=inactive]:hidden lg:!block">
            <ConsolaRag expedienteId={id} hayIndice={hayIndice} alAbrirCita={setCitaAbierta} />
          </Tabs.Content>
        </div>
      </Tabs.Root>

      {/* Portal: la página tiene una animación con transform, que convertiría el `fixed` del
          visor en relativo a ese contenedor. */}
      {citaAbierta &&
        createPortal(
          <Suspense
            fallback={
              <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 text-white ">
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

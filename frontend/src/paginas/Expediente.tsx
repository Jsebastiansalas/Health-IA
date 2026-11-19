import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/cliente";
import type { Cita, Documento, Expediente } from "../api/tipos";
import { ConsolaRag } from "../componentes/ConsolaRag";
import { PanelDocumentos } from "../componentes/PanelDocumentos";
import { esConsultable, TIPOS_EXPEDIENTE } from "../lib/formato";

// PDF.js (~1,3 MB con su worker) solo se descarga cuando se abre una cita.
const VisorLocal = lazy(() => import("../componentes/VisorLocal").then((m) => ({ default: m.VisorLocal })));

export function PaginaExpediente() {
  const { id = "" } = useParams();
  const [citaAbierta, setCitaAbierta] = useState<Cita | null>(null);
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
      <div className="folio max-w-xl p-10">
        <p className="font-display text-2xl">Expediente no disponible</p>
        <p className="mt-2 text-tinta-2">{(error as Error).message}</p>
        <Link to="/" className="boton boton-linea mt-6">Volver al archivo</Link>
      </div>
    );
  }
  if (!expediente) return <p className="etiqueta">Abriendo expediente…</p>;

  const puedeSubir = expediente.mi_permiso === "ADMIN" || expediente.mi_permiso === "EDITOR";
  const hayIndice = (documentos ?? []).some((d) => esConsultable(d.estado_indexacion));

  return (
    <div className="animate-aparecer">
      <nav className="etiqueta mb-6">
        <Link to="/" className="hover:text-sello">Archivo</Link> / {expediente.codigo_expediente}
      </nav>
      <header className="mb-10 grid gap-6 border-b-2 border-tinta pb-6 md:grid-cols-[1fr_auto]">
        <div>
          <p className="font-mono text-sm text-sello">{expediente.codigo_expediente}</p>
          <h1 className="mt-1 max-w-4xl font-display text-4xl leading-tight font-light md:text-5xl">{expediente.titulo}</h1>
          <p className="mt-2 text-tinta-2">
            {expediente.entidad_contratante ?? "Entidad no registrada"} · {TIPOS_EXPEDIENTE[expediente.tipo_expediente]}
          </p>
        </div>
        <dl className="grid grid-cols-2 gap-x-8 gap-y-2 self-end text-sm">
          <dt className="etiqueta">Estado</dt>
          <dd>{expediente.estado}</dd>
          <dt className="etiqueta">Índice</dt>
          <dd className="font-mono text-xs">{expediente.embedding_model_activo}</dd>
          <dt className="etiqueta">Su permiso</dt>
          <dd>{expediente.mi_permiso}</dd>
        </dl>
      </header>

      <div className="grid gap-12 lg:grid-cols-[minmax(320px,430px)_1fr]">
        <PanelDocumentos expedienteId={id} puedeSubir={puedeSubir && expediente.estado === "ABIERTO"} />
        <ConsolaRag expedienteId={id} hayIndice={hayIndice} alAbrirCita={setCitaAbierta} />
      </div>

      {/* Portal: la página tiene una animación con transform, que convertiría el `fixed` del
          visor en relativo a ese contenedor. */}
      {citaAbierta &&
        createPortal(
          <Suspense fallback={<div className="etiqueta fixed inset-0 z-50 grid place-items-center bg-tinta/40">Abriendo visor…</div>}>
            <VisorLocal cita={citaAbierta} alCerrar={() => setCitaAbierta(null)} />
          </Suspense>,
          document.body,
        )}
    </div>
  );
}

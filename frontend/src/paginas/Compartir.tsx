import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/cliente";
import type { Expediente } from "../api/tipos";
import { FormularioSubida } from "../componentes/PanelDocumentos";
import { Boton } from "../componentes/ui/Boton";
import { Esqueleto } from "../componentes/ui/Esqueleto";
import { FileText, ShareNetwork } from "../iconos";
import { cn } from "../lib/cn";
import { descartarCompartido, useCompartido } from "../lib/compartido";
import { useConsentimiento } from "../lib/consentimiento";

const tamano = (b: number) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`);

/**
 * Llegada desde «Compartir» (Android y escritorio): el service worker dejó la foto o el PDF en el teléfono y aquí
 * se elige a qué expediente subirlo. Al subirlo o cancelar, el archivo se borra del teléfono.
 */
export function PaginaCompartir() {
  const navegar = useNavigate();
  const { archivo, cargando } = useCompartido();
  const consentimiento = useConsentimiento();
  const [elegido, setElegido] = useState<Expediente | null>(null);
  const { data: expedientes, isLoading } = useQuery({
    queryKey: ["expedientes"],
    queryFn: () => api<Expediente[]>("/expedientes?limit=200"),
    enabled: !!archivo,
  });
  const destinos = (expedientes ?? []).filter((e) => e.estado === "ABIERTO" && (e.mi_permiso === "ADMIN" || e.mi_permiso === "EDITOR"));

  async function cancelar() {
    await descartarCompartido();
    navegar("/");
  }

  if (cargando) return <Esqueleto className="h-40 rounded-xl" aria-busy />;

  if (!archivo) {
    return (
      <section className="panel mx-auto max-w-xl p-8">
        <h1 className="flex items-center gap-3 text-xl font-semibold">
          <ShareNetwork className="size-6 text-primario" aria-hidden />
          No llegó ningún archivo
        </h1>
        <p className="mt-2 text-texto-2">
          Comparte una foto o un PDF desde otra aplicación y elige MedTender. También puedes subirlo desde un expediente.
        </p>
        <Link to="/" className="mt-6 inline-block">
          <Boton variante="primario">Ir a mis expedientes</Boton>
        </Link>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-2xl space-y-6" aria-labelledby="titulo-compartir">
      <div>
        <h1 id="titulo-compartir" className="text-3xl font-semibold">
          ¿A qué expediente lo subo?
        </h1>
        <p className="mt-3 flex items-center gap-3 text-texto-2">
          <FileText className="size-5 shrink-0 text-primario" aria-hidden />
          <span className="min-w-0 truncate">
            <span className="font-medium text-texto">{archivo.name || "Archivo compartido"}</span> · {tamano(archivo.size)}
          </span>
        </p>
      </div>

      {consentimiento.bloqueado ? (
        <p role="alert" className="panel p-4 text-sm text-texto-2">
          Antes de subir documentos tienes que aceptar el consentimiento y confirmar tu correo. Hazlo desde tus expedientes y vuelve a
          compartir el archivo.
        </p>
      ) : elegido ? (
        <div className="space-y-3">
          <p className="text-sm text-texto-2">
            Expediente: <span className="font-medium text-texto">{elegido.titulo}</span>{" "}
            <button type="button" className="underline underline-offset-4 hover:text-texto" onClick={() => setElegido(null)}>
              Cambiar
            </button>
          </p>
          <FormularioSubida
            expedienteId={elegido.id}
            clinico={elegido.tipo_expediente === "AUDITORIA_CLINICA"}
            archivoInicial={archivo}
            alSubir={() => {
              void descartarCompartido().then(() => navegar(`/expedientes/${elegido.id}`));
            }}
          />
        </div>
      ) : (
        <fieldset>
          <legend className="text-sm font-medium text-texto-2">Elige un expediente abierto</legend>
          {isLoading && <Esqueleto className="mt-3 h-32 rounded-xl" />}
          {!isLoading && destinos.length === 0 && (
            <p className="mt-3 text-sm text-texto-2">
              No tienes expedientes abiertos donde puedas subir documentos. <Link to="/" className="underline underline-offset-4">Crea uno</Link> y vuelve a compartir el
              archivo.
            </p>
          )}
          <ul className="mt-3 space-y-2">
            {destinos.map((e) => (
              <li key={e.id}>
                <button
                  type="button"
                  onClick={() => setElegido(e)}
                  className={cn(
                    "panel flex w-full items-center justify-between gap-4 p-4 text-left transition-colors duration-300 hover:border-primario/60",
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{e.titulo}</span>
                    <span className="etiqueta">{e.codigo_expediente}</span>
                  </span>
                  <span className="shrink-0 text-sm font-medium text-primario-osc">Elegir</span>
                </button>
              </li>
            ))}
          </ul>
        </fieldset>
      )}

      <Boton variante="fantasma" onClick={() => void cancelar()}>
        Cancelar y borrar el archivo del teléfono
      </Boton>
    </section>
  );
}

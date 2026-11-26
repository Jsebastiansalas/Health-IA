import { useState } from "react";
import { BotonLeer } from "../componentes/BotonLeer";
import { guardarPreferencias, leerPreferencias, type Letra, type Preferencias } from "../lib/accesibilidad";
import { useVoz } from "../lib/voz";

const TAMANOS: [Letra, string][] = [
  ["normal", "Normal"],
  ["grande", "Grande"],
  ["muy-grande", "Muy grande"],
];

export function PaginaAccesibilidad() {
  const [p, setP] = useState(leerPreferencias);
  const { disponible } = useVoz();
  const cambiar = (nuevas: Preferencias) => {
    setP(nuevas);
    guardarPreferencias(nuevas);
  };
  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-semibold">Accesibilidad</h1>
      <p className="mt-2 text-texto-2">Estos ajustes se guardan solo en este equipo.</p>

      <fieldset className="panel mt-6 p-6">
        <legend className="float-left mb-3 w-full text-xl font-semibold">Tamaño de la letra</legend>
        <div className="clear-left flex flex-wrap gap-3">
          {TAMANOS.map(([valor, nombre]) => (
            <label key={valor} className="flex cursor-pointer items-center gap-2 rounded-lg border border-borde px-4 py-3 has-checked:border-primario">
              <input type="radio" name="letra" checked={p.letra === valor} onChange={() => cambiar({ ...p, letra: valor })} />
              {nombre}
            </label>
          ))}
        </div>
      </fieldset>

      <section className="panel mt-6 p-6">
        <label className="flex cursor-pointer items-start gap-3">
          <input type="checkbox" className="mt-1" checked={p.contraste} onChange={(e) => cambiar({ ...p, contraste: e.target.checked })} />
          <span>
            <span className="block text-xl font-semibold">Alto contraste</span>
            <span className="block text-sm text-texto-2">Texto más oscuro (o más claro en el tema oscuro) y bordes marcados.</span>
          </span>
        </label>
      </section>

      <section className="panel mt-6 p-6" aria-labelledby="titulo-voz">
        <h2 id="titulo-voz" className="text-xl font-semibold">
          Lectura en voz alta
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-texto-2">
          En las explicaciones de documentos aparece el botón «Escuchar». Usa una voz instalada en tu equipo: el texto no se
          envía a nadie para leerlo.
        </p>
        <div className="mt-4">
          {disponible ? (
            <BotonLeer texto="Así suena la lectura en voz alta de MedTender." />
          ) : (
            <p role="status" className="text-sm">
              Este equipo no tiene una voz en español instalada. Puedes agregarla en los ajustes de idioma o de voz del sistema y
              volver a abrir el navegador. No usamos voces en internet porque enviarían tu información de salud a otra empresa.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

import { SpeakerHigh, StopCircle } from "../iconos";
import { useVoz } from "../lib/voz";
import { Boton } from "./ui/Boton";

/** «Escuchar» un texto. No aparece si el equipo no tiene una voz local en español. */
export function BotonLeer({ texto }: { texto: string }) {
  const { disponible, leyendo, leer, detener } = useVoz();
  if (!disponible) return null;
  return leyendo ? (
    <Boton type="button" variante="secundario" tamano="sm" onClick={detener}>
      <StopCircle className="size-4" aria-hidden />
      Detener la lectura
    </Boton>
  ) : (
    <Boton type="button" variante="secundario" tamano="sm" onClick={() => leer(texto)}>
      <SpeakerHigh className="size-4" aria-hidden />
      Escuchar
    </Boton>
  );
}

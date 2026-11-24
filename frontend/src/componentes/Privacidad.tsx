import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Eraser, Trash2 } from "../iconos";
import { useState } from "react";
import { toast } from "sonner";
import { api, post } from "../api/cliente";
import { useSesion } from "../sesion";
import { Boton } from "./ui/Boton";
import { Campo } from "./ui/Campo";
import { Dialogo } from "./ui/Dialogo";

/** Borra las preguntas y respuestas guardadas de un expediente (los documentos no se tocan). */
export function BotonBorrarHistorial({ expedienteId }: { expedienteId: string }) {
  const cliente = useQueryClient();
  const [abierto, setAbierto] = useState(false);
  const borrar = useMutation({
    mutationFn: () => api<void>(`/expedientes/${expedienteId}/consultas`, { method: "DELETE" }),
    onSuccess: () => {
      cliente.setQueryData(["consultas", expedienteId], []);
      toast.success("Historial borrado", { description: "Se eliminaron las preguntas y respuestas guardadas." });
      setAbierto(false);
    },
  });
  return (
    <>
      <Boton variante="fantasma" tamano="sm" onClick={() => setAbierto(true)}>
        <Eraser className="size-4" aria-hidden />
        Borrar historial de preguntas
      </Boton>
      <Dialogo
        abierto={abierto}
        alCambiar={setAbierto}
        tipo="centro"
        titulo="¿Borrar el historial de preguntas?"
        descripcion="Se eliminan las preguntas y respuestas guardadas de este expediente. Los documentos no se tocan."
      >
        {borrar.error && (
          <p role="alert" className="mb-4 text-sm text-peligro">
            {(borrar.error as Error).message}
          </p>
        )}
        <div className="flex justify-end gap-3">
          <Boton variante="secundario" onClick={() => setAbierto(false)}>
            Cancelar
          </Boton>
          <Boton variante="peligro" onClick={() => borrar.mutate()} cargando={borrar.isPending}>
            Borrar historial
          </Boton>
        </div>
      </Dialogo>
    </>
  );
}

/** Elimina la cuenta personal con todo su contenido. Pide la contraseña porque no se puede deshacer. */
export function DialogoEliminarCuenta({ abierto, alCambiar }: { abierto: boolean; alCambiar: (a: boolean) => void }) {
  const { salir } = useSesion();
  const [password, setPassword] = useState("");
  const eliminar = useMutation({
    mutationFn: () => post<void>("/cuenta/eliminar", { password }),
    onSuccess: () => {
      toast.success("Cuenta eliminada", { description: "Se borraron tus documentos, preguntas y datos." });
      salir();
    },
  });
  return (
    <Dialogo
      abierto={abierto}
      alCambiar={(a) => {
        if (!a) setPassword("");
        alCambiar(a);
      }}
      tipo="centro"
      titulo="Eliminar mi cuenta"
      descripcion="Se borran tus expedientes, documentos, preguntas y tus datos. No se puede deshacer."
    >
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          eliminar.mutate();
        }}
      >
        <Campo etiqueta="Escribe tu contraseña para confirmar" type="password" autoComplete="current-password" required
          value={password} onChange={(e) => setPassword(e.target.value)} />
        {eliminar.error && (
          <p role="alert" className="text-sm text-peligro">
            {(eliminar.error as Error).message}
          </p>
        )}
        <div className="flex justify-end gap-3">
          <Boton type="button" variante="secundario" onClick={() => alCambiar(false)}>
            Cancelar
          </Boton>
          <Boton type="submit" variante="peligro" cargando={eliminar.isPending} disabled={password.length === 0}>
            <Trash2 className="size-4" aria-hidden />
            Eliminar para siempre
          </Boton>
        </div>
      </form>
    </Dialogo>
  );
}

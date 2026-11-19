import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ErrorApi } from "./api/cliente";
import "./index.css";
import { Marco } from "./componentes/Marco";
import { PaginaExpediente } from "./paginas/Expediente";
import { PaginaExpedientes } from "./paginas/Expedientes";
import { PaginaIngreso } from "./paginas/Ingreso";
import { ProveedorSesion, useSesion } from "./sesion";

const consultas = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (intentos, error) => !(error instanceof ErrorApi && error.status < 500) && intentos < 2,
      refetchOnWindowFocus: false,
    },
  },
});

function Rutas() {
  const { autenticado } = useSesion();
  if (!autenticado) return <PaginaIngreso />;
  return (
    <Marco>
      <Routes>
        <Route path="/" element={<PaginaExpedientes />} />
        <Route path="/expedientes/:id" element={<PaginaExpediente />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Marco>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={consultas}>
      <BrowserRouter>
        <ProveedorSesion>
          <Rutas />
        </ProveedorSesion>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);

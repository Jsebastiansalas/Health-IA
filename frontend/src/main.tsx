import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ErrorApi } from "./api/cliente";
import "./index.css";
import { Marco } from "./componentes/Marco";

import { ProveedorSesion, useSesion } from "./sesion";

// Cada pantalla es su propio paquete: quien aún no ingresó no descarga la aplicación, y viceversa.
const PaginaBienvenida = lazy(() => import("./paginas/Bienvenida").then((m) => ({ default: m.PaginaBienvenida })));
const PaginaRegistro = lazy(() => import("./paginas/Registro").then((m) => ({ default: m.PaginaRegistro })));
const PaginaIngreso = lazy(() => import("./paginas/Ingreso").then((m) => ({ default: m.PaginaIngreso })));
const PaginaExpedientes = lazy(() => import("./paginas/Expedientes").then((m) => ({ default: m.PaginaExpedientes })));
const PaginaMedicamentos = lazy(() => import("./paginas/Medicamentos").then((m) => ({ default: m.PaginaMedicamentos })));
const PaginaExpediente = lazy(() => import("./paginas/Expediente").then((m) => ({ default: m.PaginaExpediente })));

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
  if (!autenticado) {
    return (
      <Routes>
        <Route path="/" element={<PaginaBienvenida />} />
        <Route path="/ingreso" element={<PaginaIngreso />} />
        <Route path="/registro" element={<PaginaRegistro />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    );
  }
  return (
    <Marco>
      <Routes>
        <Route path="/" element={<PaginaExpedientes />} />
        <Route path="/ingreso" element={<Navigate to="/" replace />} />
        <Route path="/registro" element={<Navigate to="/" replace />} />
        <Route path="/medicamentos" element={<PaginaMedicamentos />} />
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
          <Suspense fallback={<div className="min-h-screen" aria-busy />}>
            <Rutas />
          </Suspense>
        </ProveedorSesion>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);

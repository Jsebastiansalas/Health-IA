import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { activarRastreo } from "./lib/errores";
import { ErrorApi } from "./api/cliente";
import "./index.css";
import { aplicarPreferencias } from "./lib/accesibilidad";
import { AvisosApp } from "./componentes/AvisosApp";
import { Marco } from "./componentes/Marco";
import { aplicarVersionNueva, registrarApp } from "./pwa";

import { ProveedorSesion, useSesion } from "./sesion";

// Cada pantalla es su propio paquete: quien aún no ingresó no descarga la aplicación, y viceversa.
const PaginaBienvenida = lazy(() => import("./paginas/Bienvenida").then((m) => ({ default: m.PaginaBienvenida })));
const PaginaPersonas = lazy(() => import("./paginas/Bienvenida").then((m) => ({ default: m.PaginaPersonas })));
const PaginaPrivacidad = lazy(() => import("./paginas/Legal").then((m) => ({ default: m.PaginaPrivacidad })));
const PaginaTerminos = lazy(() => import("./paginas/Legal").then((m) => ({ default: m.PaginaTerminos })));
const PaginaNoEncontrada = lazy(() => import("./paginas/Legal").then((m) => ({ default: m.PaginaNoEncontrada })));
const PaginaRegistro = lazy(() => import("./paginas/Registro").then((m) => ({ default: m.PaginaRegistro })));
const PaginaVerificarCorreo = lazy(() => import("./paginas/VerificarCorreo").then((m) => ({ default: m.PaginaVerificarCorreo })));
const PaginaIngreso = lazy(() => import("./paginas/Ingreso").then((m) => ({ default: m.PaginaIngreso })));
const PaginaExpedientes = lazy(() => import("./paginas/Expedientes").then((m) => ({ default: m.PaginaExpedientes })));
const PaginaMedicamentos = lazy(() => import("./paginas/Medicamentos").then((m) => ({ default: m.PaginaMedicamentos })));
const PaginaRecordatorios = lazy(() => import("./paginas/Recordatorios").then((m) => ({ default: m.PaginaRecordatorios })));
const PaginaOlvideContrasena = lazy(() => import("./paginas/Contrasena").then((m) => ({ default: m.PaginaOlvideContrasena })));
const PaginaRestablecer = lazy(() => import("./paginas/Contrasena").then((m) => ({ default: m.PaginaRestablecer })));
const PaginaAccesibilidad = lazy(() => import("./paginas/Accesibilidad").then((m) => ({ default: m.PaginaAccesibilidad })));
const PaginaSeguridad = lazy(() => import("./paginas/Seguridad").then((m) => ({ default: m.PaginaSeguridad })));
const PaginaMisDatos = lazy(() => import("./paginas/MisDatos").then((m) => ({ default: m.PaginaMisDatos })));
const PaginaCompartir = lazy(() => import("./paginas/Compartir").then((m) => ({ default: m.PaginaCompartir })));
const PaginaExpediente = lazy(() => import("./paginas/Expediente").then((m) => ({ default: m.PaginaExpediente })));
const PaginaInvitacion = lazy(() => import("./paginas/Invitacion").then((m) => ({ default: m.PaginaInvitacion })));

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
        {/* El producto principal es el de las personas; las organizaciones tienen su portada aparte. */}
        <Route path="/" element={<PaginaPersonas />} />
        <Route path="/organizaciones" element={<PaginaBienvenida />} />
        <Route path="/ingreso" element={<PaginaIngreso />} />
        <Route path="/registro" element={<PaginaRegistro />} />
        <Route path="/personas" element={<Navigate to="/" replace />} />
        <Route path="/verificar-correo" element={<PaginaVerificarCorreo />} />
        <Route path="/olvide-contrasena" element={<PaginaOlvideContrasena />} />
        <Route path="/restablecer" element={<PaginaRestablecer />} />
        <Route path="/invitacion" element={<PaginaInvitacion conSesion={false} />} />
        <Route path="/privacidad" element={<PaginaPrivacidad />} />
        <Route path="/terminos" element={<PaginaTerminos />} />
        {/* Llegó un archivo desde «Compartir» sin sesión: queda guardado en el teléfono y se ofrece al ingresar. */}
        <Route path="/compartir" element={<Navigate to="/ingreso" replace />} />
        <Route path="*" element={<PaginaNoEncontrada />} />
      </Routes>
    );
  }
  return (
    <Marco>
      <Routes>
        <Route path="/" element={<PaginaExpedientes />} />
        <Route path="/ingreso" element={<Navigate to="/" replace />} />
        <Route path="/registro" element={<Navigate to="/" replace />} />
        <Route path="/verificar-correo" element={<PaginaVerificarCorreo />} />
        <Route path="/medicamentos" element={<PaginaMedicamentos />} />
        <Route path="/expedientes/:id" element={<PaginaExpediente />} />
        <Route path="/compartir" element={<PaginaCompartir />} />
        <Route path="/invitacion" element={<PaginaInvitacion conSesion />} />
        <Route path="/recordatorios" element={<PaginaRecordatorios />} />
        <Route path="/cuenta/seguridad" element={<PaginaSeguridad />} />
        <Route path="/cuenta/datos" element={<PaginaMisDatos />} />
        <Route path="/cuenta/accesibilidad" element={<PaginaAccesibilidad />} />
        <Route path="/restablecer" element={<PaginaRestablecer />} />
        <Route path="/privacidad" element={<PaginaPrivacidad />} />
        <Route path="/terminos" element={<PaginaTerminos />} />
        <Route path="*" element={<PaginaNoEncontrada />} />
      </Routes>
    </Marco>
  );
}

aplicarPreferencias(); // antes de pintar, para que no salte el tamaño

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={consultas}>
      <BrowserRouter>
        <ProveedorSesion>
          <Suspense fallback={<div className="min-h-screen" aria-busy />}>
            <Rutas />
          </Suspense>
          <AvisosApp alActualizar={aplicarVersionNueva} />
        </ProveedorSesion>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);

void activarRastreo(import.meta.env.VITE_ERRORES_DSN as string | undefined);
registrarApp();

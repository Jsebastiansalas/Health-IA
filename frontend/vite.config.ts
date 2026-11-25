/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

declare const process: { env: Record<string, string | undefined> };

// En desarrollo, /api se reenvía a la API Java (docker compose la publica en el 8010).
// Así no hace falta CORS y la File System Access API funciona en localhost (contexto seguro).
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // App instalable (PWA). El service worker propio está en src/sw.ts: solo guarda el armazón de la app,
    // nunca datos de /api, y recibe los archivos de «Compartir».
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.ts",
      registerType: "prompt",
      injectRegister: false,
      injectManifest: {
        globPatterns: ["**/*.{js,css,html,woff2,svg,png}"],
        // Los videos e imágenes de la portada no van al teléfono: se descargan solo al verla.
        globIgnores: ["recorrido/**"],
      },
      manifest: {
        id: "/",
        name: "MedTender",
        short_name: "MedTender",
        description: "Entiende tus documentos de salud con la fuente a la vista. No diagnostica ni receta.",
        lang: "es",
        dir: "ltr",
        start_url: "/",
        scope: "/",
        display: "standalone",
        orientation: "any",
        background_color: "#f4f7fa",
        theme_color: "#f4f7fa",
        categories: ["medical", "health", "productivity"],
        icons: [
          { src: "/icono-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
          { src: "/icono-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
          { src: "/icono-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
        shortcuts: [{ name: "Medicamentos", url: "/medicamentos", icons: [{ src: "/icono-192.png", sizes: "192x192" }] }],
        share_target: {
          action: "/compartir",
          method: "POST",
          enctype: "multipart/form-data",
          params: {
            files: [
              {
                name: "archivo",
                accept: ["application/pdf", "image/jpeg", "image/png", "image/heic", "image/heif", ".pdf", ".jpg", ".jpeg", ".png", ".heic", ".heif"],
              },
            ],
          },
        },
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: { "/api": process.env.MEDTENDER_API ?? "http://localhost:8010" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // En Windows, con los 11 archivos en paralelo, la portada completa tarda más de los 5 s por defecto.
    testTimeout: 15000,
  },
});

/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

declare const process: { env: Record<string, string | undefined> };

// En desarrollo, /api se reenvía a la API Java (docker compose la publica en el 8010).
// Así no hace falta CORS y la File System Access API funciona en localhost (contexto seguro).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: { "/api": process.env.MEDTENDER_API ?? "http://localhost:8010" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});

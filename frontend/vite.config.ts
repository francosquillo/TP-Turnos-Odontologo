import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Shell C-01: dev contra la api local (VITE_API_URL) o el proxy.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/health": {
        target: process.env.VITE_API_URL ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    // Solo se procesa en tests el CSS que los tests de tokens leen con ?raw (C-08, C-09).
    css: { include: [/odontograma\.css/, /presupuestos\.css/, /cuenta-corriente\.css/, /caja\.css/, /liquidaciones\.css/, /tokens\.css/] },
  },
});

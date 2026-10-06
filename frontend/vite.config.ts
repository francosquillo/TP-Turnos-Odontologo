import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Shell C-01: dev contra la api local (VITE_API_URL) o el proxy.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
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
  },
});

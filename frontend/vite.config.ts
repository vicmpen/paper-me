/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served by FastAPI under /paper/ (assets at /paper/assets/*). In dev, Vite
// proxies the JSON/SSE API to the Python server.
export default defineConfig({
  base: "/paper/",
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.ts"] },
});

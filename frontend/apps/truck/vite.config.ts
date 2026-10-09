import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// API calls go through the dev server so the browser sees one origin (session cookie + CSRF, see D-008).
const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5174,
    strictPort: true,
    proxy: { "/api": { target: apiTarget, changeOrigin: false } },
  },
  preview: { port: 5174, strictPort: true },
});

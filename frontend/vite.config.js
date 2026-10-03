import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: process.env.VITE_BASE_PATH || "/",
  plugins: [react()],
  server: {
    port: 5173,
    // In development the UI calls /api on its own origin and Vite forwards it to FastAPI,
    // so no CORS setup is needed locally.
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});

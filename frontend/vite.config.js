import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api to FastAPI so no CORS setup is needed locally.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
});

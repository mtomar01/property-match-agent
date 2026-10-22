import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, Vite serves the app and passes /api to the Python server (api/server.py).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
});

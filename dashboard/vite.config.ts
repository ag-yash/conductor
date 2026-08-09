import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The proxy keeps browser code same-origin during local development. The
// dashboard therefore calls /api/v1, while Vite forwards it to FastAPI.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8080",
    },
  },
});

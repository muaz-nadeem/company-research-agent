import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  build: { rollupOptions: { output: { manualChunks: { markdown: ['react-markdown', 'remark-gfm'], auth: ['@supabase/supabase-js'] } } } },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: loadEnv(mode, '.', '').API_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
}));

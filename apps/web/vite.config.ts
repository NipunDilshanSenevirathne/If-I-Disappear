import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/** Preload the two Latin font files the first screen needs, so headings don't wait for the CSS. */
function preloadFonts(): Plugin {
  return {
    name: "iid-preload-fonts",
    apply: "build",
    transformIndexHtml: {
      order: "post",
      handler(html, ctx) {
        const files = Object.keys(ctx.bundle ?? {}).filter((f) => /(bricolage-grotesque-latin-opsz|figtree-latin-wght)-normal-[\w-]+\.woff2$/.test(f));
        return {
          html,
          tags: files.map((f) => ({ tag: "link", attrs: { rel: "preload", as: "font", type: "font/woff2", href: `/${f}`, crossorigin: "" }, injectTo: "head" as const })),
        };
      },
    },
  };
}

// In development the API runs on :8080 (uvicorn). In production the API serves the built app
// (or Firebase Hosting rewrites /api/** to the Cloud Run service), so the same relative URLs work.
export default defineConfig({
  plugins: [react(), preloadFonts()],
  server: {
    port: 5173,
    proxy: { "/api": { target: process.env.API_URL ?? "http://127.0.0.1:8080", changeOrigin: true } },
  },
  preview: {
    port: 4173,
    proxy: { "/api": { target: process.env.API_URL ?? "http://127.0.0.1:8080", changeOrigin: true } },
  },
  build: {
    target: "es2022",
    sourcemap: true,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-dom/client", "react-router-dom"],
          genai: ["@google/genai"],
          firebase: ["firebase/app", "firebase/auth"],
        },
      },
    },
  },
});

import { defineConfig } from "vite";

// Flask serves the bundle through the companion blueprint's static folder, and
// names the entry files itself in the page template, so the output names are
// fixed rather than hashed.
export default defineConfig({
  base: "/companion/static/web/",
  build: {
    outDir: "../btcopilot/companion/static/web",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "app.js",
        chunkFileNames: "app-[name].js",
        assetFileNames: "app.[ext]",
      },
    },
  },
  server: { proxy: { "/companion": "http://127.0.0.1:8889" } },
});

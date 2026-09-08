/// <reference types="vitest" />
import { defineConfig } from "vite";

// Flask serves the bundle through the personal blueprint's static folder, and
// names the entry files itself in the page template, so the output names are
// fixed rather than hashed.
export default defineConfig({
  base: "/personal/static/web/",
  build: {
    outDir: "../btcopilot/personal/static/web",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "app.js",
        chunkFileNames: "app-[name].js",
        assetFileNames: "app.[ext]",
      },
    },
  },
  server: { proxy: { "/personal": "http://127.0.0.1:8889" } },
  // Playwright owns tests/visual; vitest owns the pure unit tests only.
  test: { include: ["test/**/*.test.ts"] },
});

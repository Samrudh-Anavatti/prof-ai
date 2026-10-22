/// <reference types="node" />
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

const MATHLIVE_FONTS = "node_modules/mathlive/fonts";
const FONTS_URL = "/assets/mathlive/fonts";

/** MathLive's fonts at FONTS_URL (src/mathlive.ts), since the CSP blocks its default CDN. */
function mathliveFonts(): Plugin {
  return {
    name: "mathlive-fonts",
    configureServer(server) {
      server.middlewares.use(FONTS_URL, (request, response, next) => {
        const name = (request.url ?? "").replace(/^\//, "").split("?")[0];
        if (!readdirSync(MATHLIVE_FONTS).includes(name)) return next();
        response.setHeader("Content-Type", "font/woff2");
        response.end(readFileSync(join(MATHLIVE_FONTS, name)));
      });
    },
    generateBundle() {
      for (const name of readdirSync(MATHLIVE_FONTS)) {
        this.emitFile({
          type: "asset",
          fileName: `${FONTS_URL.slice(1)}/${name}`,
          source: readFileSync(join(MATHLIVE_FONTS, name)),
        });
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), mathliveFonts()],
  build: {
    outDir: "../src/prof_ai/static",
    emptyOutDir: true,
  },
  server: {
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "node",
  },
});

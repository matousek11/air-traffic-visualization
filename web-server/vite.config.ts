import { defineConfig } from "vite";

export default defineConfig({
  root: ".",
  build: {
    outDir: "static/build",
    emptyOutDir: true,
    rollupOptions: {
      input: "static/js/main.ts", // point directly to your TS entry
      output: {
        entryFileNames: `main.js`, // no hash
        chunkFileNames: `[name].js`,
        assetFileNames: `[name].[ext]`
      }
    }
  },
});
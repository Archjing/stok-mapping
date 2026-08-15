import { defineConfig } from 'vite';

export default defineConfig({
  // Relative base so the built dist/ can be served from any sub-path.
  base: './',
  server: {
    port: 5180,
    open: false,
  },
  build: {
    outDir: 'dist',
    target: 'es2020',
    rollupOptions: {
      output: {
        // IIFE + 单 chunk：配合 scripts/inline-dist.mjs 把 JS/CSS 内联进
        // dist/index.html，产出双击即用的单文件（file:// 也能打开）。
        format: 'iife',
        inlineDynamicImports: true,
        entryFileNames: 'app.js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
});

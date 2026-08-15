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
  },
});

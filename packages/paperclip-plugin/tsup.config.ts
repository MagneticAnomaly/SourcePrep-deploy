import { defineConfig } from 'tsup';

export default defineConfig([
  // Worker bundle (Node.js, runs as subprocess)
  {
    entry: { worker: 'src/worker/index.ts' },
    format: ['esm'],
    target: 'node20',
    platform: 'node',
    outDir: 'dist',
    clean: true,
    sourcemap: true,
    external: ['@paperclipai/plugin-sdk'],
  },
  // Manifest (imported by host at install time)
  {
    entry: { manifest: 'src/manifest.ts' },
    format: ['esm'],
    target: 'node20',
    platform: 'node',
    outDir: 'dist',
    sourcemap: true,
    external: ['@paperclipai/plugin-sdk'],
  },
  // UI bundle (browser, loaded by Paperclip dashboard)
  {
    entry: { 'ui/index': 'src/ui/index.ts' },
    format: ['esm'],
    target: 'es2022',
    platform: 'browser',
    outDir: 'dist',
    sourcemap: true,
    jsx: 'automatic',
    external: ['@paperclipai/plugin-sdk', '@paperclipai/plugin-sdk/ui', 'react', 'react-dom'],
  },
]);

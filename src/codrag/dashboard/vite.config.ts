import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const uiSrcPath = new URL('../../../packages/ui/src', import.meta.url).pathname
const repoRootPath = new URL('../../..', import.meta.url).pathname

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      // Bare import '@codrag/ui' -> index.ts
      { find: /^@codrag\/ui$/, replacement: `${uiSrcPath}/index.ts` },
      // Sub-path imports '@codrag/ui/foo' -> src/foo
      { find: /^@codrag\/ui\/(.*)$/, replacement: `${uiSrcPath}/$1` },
    ],
    extensions: ['.ts', '.tsx', '.js', '.jsx', '.json'],
  },
  server: {
    host: '0.0.0.0',
    cors: true,
    port: 5174,
    strictPort: true,
    fs: {
      allow: [repoRootPath],
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8400',
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('[Vite Proxy] Error:', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('[Vite Proxy] Request:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('[Vite Proxy] Response:', proxyRes.statusCode, req.url);
          });
        },
      },
      '/projects': {
        target: 'http://127.0.0.1:8400',
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('[Vite Proxy] Error:', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('[Vite Proxy] Request:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('[Vite Proxy] Response:', proxyRes.statusCode, req.url);
          });
        },
      },
      '/health': {
        target: 'http://127.0.0.1:8400',
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('[Vite Proxy] Error:', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('[Vite Proxy] Request:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('[Vite Proxy] Response:', proxyRes.statusCode, req.url);
          });
        },
      },
      '/llm': {
        target: 'http://127.0.0.1:8400',
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('[Vite Proxy] Error:', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('[Vite Proxy] Request:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('[Vite Proxy] Response:', proxyRes.statusCode, req.url);
          });
        },
      },
      '/global': {
        target: 'http://127.0.0.1:8400',
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('[Vite Proxy] Error:', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('[Vite Proxy] Request:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('[Vite Proxy] Response:', proxyRes.statusCode, req.url);
          });
        },
      },
      '/events': {
        target: 'http://127.0.0.1:8400',
        changeOrigin: true,
        secure: false,
        // SSE: disable response buffering so events stream through immediately
        configure: (proxy, _options) => {
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('[Vite Proxy] SSE Request:', req.method, req.url);
          });
          proxy.on('error', (err, _req, _res) => {
            console.log('[Vite Proxy] SSE Error:', err);
          });
        },
      },
      '/license': {
        target: 'http://127.0.0.1:8400',
        changeOrigin: true,
        secure: false,
      },
      '/embedding': {
        target: 'http://127.0.0.1:8400',
        changeOrigin: true,
        secure: false,
      },
      '/compression': {
        target: 'http://127.0.0.1:8400',
        changeOrigin: true,
        secure: false,
      },
      '/mcp': {
        target: 'http://127.0.0.1:8400',
        changeOrigin: true,
        secure: false,
      },
      '/settings': {
        target: 'http://127.0.0.1:8400',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})

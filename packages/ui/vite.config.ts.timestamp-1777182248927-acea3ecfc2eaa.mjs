// vite.config.ts
import { defineConfig } from "file:///Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/node_modules/vite/dist/node/index.js";
import react from "file:///Volumes/4TB-BAD/HumanAI/CoDRAG/node_modules/@vitejs/plugin-react/dist/index.js";
import dts from "file:///Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/node_modules/vite-plugin-dts/dist/index.mjs";
import { resolve } from "path";
var __vite_injected_original_dirname = "/Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui";
var vite_config_default = defineConfig({
  plugins: [
    react(),
    dts({
      insertTypesEntry: true
    })
  ],
  build: {
    lib: {
      entry: resolve(__vite_injected_original_dirname, "src/index.ts"),
      name: "PrepUI",
      formats: ["es"],
      fileName: "index"
    },
    rollupOptions: {
      external: [
        "react",
        "react-dom",
        "react/jsx-runtime",
        "@radix-ui/react-slot",
        "@tremor/react",
        "class-variance-authority",
        "clsx",
        "keyboard-css",
        "lucide-react",
        "react-grid-layout",
        "react-syntax-highlighter",
        "tailwind-merge",
        // Also externalize subpaths often used
        /^@radix-ui\/.*/,
        /^react-syntax-highlighter\/.*/
      ],
      output: {
        globals: {
          react: "React",
          "react-dom": "ReactDOM"
        }
      }
    }
  },
  resolve: {
    alias: {
      "@": resolve(__vite_injected_original_dirname, "./src")
    }
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCIvVm9sdW1lcy80VEItQkFEL0h1bWFuQUkvQ29EUkFHL3BhY2thZ2VzL3VpXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ZpbGVuYW1lID0gXCIvVm9sdW1lcy80VEItQkFEL0h1bWFuQUkvQ29EUkFHL3BhY2thZ2VzL3VpL3ZpdGUuY29uZmlnLnRzXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ltcG9ydF9tZXRhX3VybCA9IFwiZmlsZTovLy9Wb2x1bWVzLzRUQi1CQUQvSHVtYW5BSS9Db0RSQUcvcGFja2FnZXMvdWkvdml0ZS5jb25maWcudHNcIjtpbXBvcnQgeyBkZWZpbmVDb25maWcgfSBmcm9tICd2aXRlJztcbmltcG9ydCByZWFjdCBmcm9tICdAdml0ZWpzL3BsdWdpbi1yZWFjdCc7XG5pbXBvcnQgZHRzIGZyb20gJ3ZpdGUtcGx1Z2luLWR0cyc7XG5pbXBvcnQgeyByZXNvbHZlIH0gZnJvbSAncGF0aCc7XG5cbmV4cG9ydCBkZWZhdWx0IGRlZmluZUNvbmZpZyh7XG4gIHBsdWdpbnM6IFtcbiAgICByZWFjdCgpLFxuICAgIGR0cyh7XG4gICAgICBpbnNlcnRUeXBlc0VudHJ5OiB0cnVlLFxuICAgIH0pLFxuICBdLFxuICBidWlsZDoge1xuICAgIGxpYjoge1xuICAgICAgZW50cnk6IHJlc29sdmUoX19kaXJuYW1lLCAnc3JjL2luZGV4LnRzJyksXG4gICAgICBuYW1lOiAnUHJlcFVJJyxcbiAgICAgIGZvcm1hdHM6IFsnZXMnXSxcbiAgICAgIGZpbGVOYW1lOiAnaW5kZXgnLFxuICAgIH0sXG4gICAgcm9sbHVwT3B0aW9uczoge1xuICAgICAgZXh0ZXJuYWw6IFtcbiAgICAgICAgJ3JlYWN0JywgXG4gICAgICAgICdyZWFjdC1kb20nLCBcbiAgICAgICAgJ3JlYWN0L2pzeC1ydW50aW1lJyxcbiAgICAgICAgJ0ByYWRpeC11aS9yZWFjdC1zbG90JyxcbiAgICAgICAgJ0B0cmVtb3IvcmVhY3QnLFxuICAgICAgICAnY2xhc3MtdmFyaWFuY2UtYXV0aG9yaXR5JyxcbiAgICAgICAgJ2Nsc3gnLFxuICAgICAgICAna2V5Ym9hcmQtY3NzJyxcbiAgICAgICAgJ2x1Y2lkZS1yZWFjdCcsXG4gICAgICAgICdyZWFjdC1ncmlkLWxheW91dCcsXG4gICAgICAgICdyZWFjdC1zeW50YXgtaGlnaGxpZ2h0ZXInLFxuICAgICAgICAndGFpbHdpbmQtbWVyZ2UnLFxuICAgICAgICAvLyBBbHNvIGV4dGVybmFsaXplIHN1YnBhdGhzIG9mdGVuIHVzZWRcbiAgICAgICAgL15AcmFkaXgtdWlcXC8uKi8sXG4gICAgICAgIC9ecmVhY3Qtc3ludGF4LWhpZ2hsaWdodGVyXFwvLiovLFxuICAgICAgXSxcbiAgICAgIG91dHB1dDoge1xuICAgICAgICBnbG9iYWxzOiB7XG4gICAgICAgICAgcmVhY3Q6ICdSZWFjdCcsXG4gICAgICAgICAgJ3JlYWN0LWRvbSc6ICdSZWFjdERPTScsXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG4gIHJlc29sdmU6IHtcbiAgICBhbGlhczoge1xuICAgICAgJ0AnOiByZXNvbHZlKF9fZGlybmFtZSwgJy4vc3JjJyksXG4gICAgfSxcbiAgfSxcbn0pO1xuIl0sCiAgIm1hcHBpbmdzIjogIjtBQUFtVCxTQUFTLG9CQUFvQjtBQUNoVixPQUFPLFdBQVc7QUFDbEIsT0FBTyxTQUFTO0FBQ2hCLFNBQVMsZUFBZTtBQUh4QixJQUFNLG1DQUFtQztBQUt6QyxJQUFPLHNCQUFRLGFBQWE7QUFBQSxFQUMxQixTQUFTO0FBQUEsSUFDUCxNQUFNO0FBQUEsSUFDTixJQUFJO0FBQUEsTUFDRixrQkFBa0I7QUFBQSxJQUNwQixDQUFDO0FBQUEsRUFDSDtBQUFBLEVBQ0EsT0FBTztBQUFBLElBQ0wsS0FBSztBQUFBLE1BQ0gsT0FBTyxRQUFRLGtDQUFXLGNBQWM7QUFBQSxNQUN4QyxNQUFNO0FBQUEsTUFDTixTQUFTLENBQUMsSUFBSTtBQUFBLE1BQ2QsVUFBVTtBQUFBLElBQ1o7QUFBQSxJQUNBLGVBQWU7QUFBQSxNQUNiLFVBQVU7QUFBQSxRQUNSO0FBQUEsUUFDQTtBQUFBLFFBQ0E7QUFBQSxRQUNBO0FBQUEsUUFDQTtBQUFBLFFBQ0E7QUFBQSxRQUNBO0FBQUEsUUFDQTtBQUFBLFFBQ0E7QUFBQSxRQUNBO0FBQUEsUUFDQTtBQUFBLFFBQ0E7QUFBQTtBQUFBLFFBRUE7QUFBQSxRQUNBO0FBQUEsTUFDRjtBQUFBLE1BQ0EsUUFBUTtBQUFBLFFBQ04sU0FBUztBQUFBLFVBQ1AsT0FBTztBQUFBLFVBQ1AsYUFBYTtBQUFBLFFBQ2Y7QUFBQSxNQUNGO0FBQUEsSUFDRjtBQUFBLEVBQ0Y7QUFBQSxFQUNBLFNBQVM7QUFBQSxJQUNQLE9BQU87QUFBQSxNQUNMLEtBQUssUUFBUSxrQ0FBVyxPQUFPO0FBQUEsSUFDakM7QUFBQSxFQUNGO0FBQ0YsQ0FBQzsiLAogICJuYW1lcyI6IFtdCn0K

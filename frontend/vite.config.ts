import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// Stable vendor bundles, pinned so their content hashes survive deploys that
// only touch app code. Rollup 5 (shipped with Vite 8) dropped the object form
// of `manualChunks`, so this map is applied by the function below instead.
const VENDOR_CHUNKS: Record<string, string[]> = {
  'vendor-react': ['react', 'react-dom', 'react-router-dom'],
  'vendor-charts': ['recharts'],
  'vendor-editor': [
    'lexical',
    '@lexical/react',
    '@lexical/rich-text',
    '@lexical/history',
    '@lexical/html',
    '@lexical/list',
  ],
  'vendor-motion': ['gsap', 'lenis', 'swiper'],
  'vendor-dnd': ['@dnd-kit/core', '@dnd-kit/sortable', '@dnd-kit/utilities'],
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/media': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  optimizeDeps: {
    include: ['swiper/react', 'swiper/modules'],
  },
  build: {
    rollupOptions: {
      output: {
        // Route-level splitting (see App.tsx) already keeps admin code out of
        // the entry chunk. Pinning the big stable vendors on top of that means
        // they keep their content hash across deploys, so returning visitors
        // re-download only the app code that actually changed.
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return undefined
          for (const [chunk, packages] of Object.entries(VENDOR_CHUNKS)) {
            // Trailing slash keeps `react` from swallowing `react-dom`.
            if (packages.some((pkg) => id.includes(`node_modules/${pkg}/`))) {
              return chunk
            }
          }
          return undefined
        },
      },
    },
    // Entry chunk should be well under this once splitting works; if the
    // warning fires again, something has been pulled back into the critical
    // path by a stray static import.
    chunkSizeWarningLimit: 600,
  },
})

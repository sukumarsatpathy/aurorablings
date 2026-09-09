import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// Stable vendor bundles, pinned so their content hashes survive deploys that
// only touch app code. Rollup 5 (shipped with Vite 8) dropped the object form
// of `manualChunks`, so this map is applied by the function below instead.
//
// ONLY pin libraries that the storefront's *eager* graph genuinely needs.
//
// This list used to also carry 'vendor-charts' (recharts), 'vendor-editor'
// (lexical), 'vendor-dnd' (@dnd-kit) and swiper. All four are reachable only
// from lazy routes -- recharts from the admin health dashboard, lexical from the
// admin rich-text editor, dnd-kit from admin sortables, swiper from the deals
// carousel. Pinning them was actively harmful.
//
// The reason is subtle. This function assigns a chunk by matching the top-level
// package path, but it does not (and cannot) pin that package's *dependency
// closure*. Rolldown therefore swept shared transitive utilities -- things
// reachable from both storefront and admin code -- into these named chunks. The
// entry then imported a single tiny helper from each:
//
//     index-*.js:  import{d as t}from"./vendor-charts-*.js"
//     index-*.js:  import{y as ae}from"./vendor-editor-*.js"
//
// One ~200 byte helper dragged the whole 351 KB recharts chunk (and 136 KB of
// lexical) onto the critical path of every storefront page load, and Vite
// emitted <link rel="modulepreload"> for both. The lazy routing was working
// correctly the entire time; the chunk *grouping* was defeating it.
//
// Unpinning them lets Rolldown place each library in the lazy chunk that
// actually uses it. Measured on a real build + headless Chromium page load:
//
//     eager critical path   1,202.6 KB -> 638.7 KB raw   (-47%)
//                             371.2 KB -> 205.3 KB gzip  (-45%)
//     homepage JS loaded      1,265,791 B -> 776,818 B   (-39%)
//     eager chunks                    18 -> 16
//
// gsap and lenis stay pinned: MainLayout pulls both eagerly (useLenis,
// useScrollReveal), so they belong in a stable long-cached chunk. swiper does
// not -- it now lands in DealSection-*.js where it belongs.
//
// Before adding anything here, confirm it is reachable from the eager graph.
// Check `dist/index.html` after a build: nothing admin-only should appear in a
// modulepreload link.
const VENDOR_CHUNKS: Record<string, string[]> = {
  'vendor-react': ['react', 'react-dom', 'react-router-dom'],
  'vendor-motion': ['gsap', 'lenis'],
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

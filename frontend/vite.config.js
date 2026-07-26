import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
    plugins: [react()],
    server: {
        host: '0.0.0.0', // Listen on all interfaces
        port: 5173,
        strictPort: true,
        hmr: {
            clientPort: 5173, // Force client to connect to port 5173
            host: 'localhost'
        },
        watch: {
            usePolling: true, // Improve file watching on Windows
        },
        proxy: {
            '/api': {
                // Env-driven so the deploy build does not bake a dev host.
                // The literal 'http://localhost:8000' is a dev-only fallback
                // for the proxy (build-time only; never bundled into client).
                target: process.env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000',
                changeOrigin: true,
                secure: false,
                ws: true // Proxy websockets if backend uses them (optional here but good practice)
            }
        }
    },
    test: {
        globals: true,
        environment: 'jsdom',
        setupFiles: './src/test/setup.js',
        exclude: ['e2e/**', 'node_modules/**'],
        css: false,
        coverage: {
            provider: 'v8',
            reporter: ['text', 'lcov'],
            include: ['src/**/*.{js,jsx}'],
            exclude: ['src/test/**', 'src/**/*.test.{js,jsx}', 'src/main.jsx'],
            // M10 — coverage gates. Conservative floor (api + state + hooks
            // are exercised; the heavier Map.jsx + Sidebar.jsx paths are
            // covered by the E2E job, not unit tests).
            thresholds: {
                lines: 60,
                statements: 60,
                functions: 55,
                branches: 50,
            },
        },
    },
})

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
                target: 'http://localhost:8000',
                changeOrigin: true,
                secure: false,
                ws: true // Proxy websockets if backend uses them (optional here but good practice)
            }
        }
    }
})

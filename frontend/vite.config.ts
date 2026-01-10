import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react({include: "**/*.tsx"})],
  server: {
    host: '0.0.0.0', // Allow external connections
    port: 5173,      // Default Vite port
    watch: {
      usePolling: true
    }
  },
})

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Lokalnie front (5173) i API (8000) to dwa procesy; na produkcji jedna domena.
    proxy: { '/api': 'http://localhost:8000' },
  },
})

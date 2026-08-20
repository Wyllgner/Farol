import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // O motor e unico; o front so conhece /api. O backend tambem serve sob
    // /api, entao aqui nao ha reescrita: o caminho que funciona em
    // desenvolvimento e exatamente o que funciona em producao.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})

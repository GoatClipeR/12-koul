import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

const r = (p: string) => fileURLToPath(new URL(p, import.meta.url))

export default defineConfig({
  base: './',
  plugins: [react()],
  build: { rollupOptions: { input: { main: r('./index.html'), smoke: r('./smoke.html'), salad: r('./salad.html') } } },
})

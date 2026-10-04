import { defineConfig } from 'vite'
// Relative base so the same build works at /<repo>/ (GitHub Pages) and /buidl/p/<slug>/ (sandbox).
export default defineConfig({ base: './', build: { target: 'es2020' } })

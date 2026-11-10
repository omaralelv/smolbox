import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { cpSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

function localPdfAssets() {
    let outputDirectory
    return {
        name: 'local-pdf-assets',
        apply: 'build',
        configResolved(config) { outputDirectory = resolve(config.root, config.build.outDir, 'pdfjs') },
        closeBundle() {
            for (const directory of ['cmaps', 'standard_fonts', 'wasm']) {
                cpSync(fileURLToPath(new URL(`./node_modules/pdfjs-dist/${directory}`, import.meta.url)),
                    resolve(outputDirectory, directory), { recursive: true })
            }
        },
    }
}

// https://vite.dev/config/
export default defineConfig({
    plugins: [react(), localPdfAssets()],

    server: {
        host: '0.0.0.0',
        allowedHosts: [
            'smolbox.vertiche.com.mx',
        ],
        proxy: {
            "/api": {
                target: "http://localhost:8000",
                changeOrigin: true,
            },
        },
    },
});

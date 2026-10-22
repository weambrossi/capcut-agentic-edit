import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { createApi } from './server/api.js';

const ROOT = fileURLToPath(new URL('..', import.meta.url));

// the dashboard's /api routes run inside the Vite server, so `npm run dev` is the whole app
const localApi = {
  name: 'local-api',
  configureServer(server) {
    const api = createApi(ROOT);
    api.sync();
    server.middlewares.use(api.handle);
  },
  configurePreviewServer(server) {
    server.middlewares.use(createApi(ROOT).handle);
  },
};

export default defineConfig({
  plugins: [react(), localApi],
  // inline config stops Vite picking up a Tailwind/PostCSS config from a parent folder
  css: { postcss: {} },
  server: {
    port: 5180,
    // skill files and reference videos change through the API; don't reload the page for them
    watch: { ignored: ['**/references/**', '**/.claude/**'] },
  },
});

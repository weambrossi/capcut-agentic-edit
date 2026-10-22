import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// skills live in ../.claude/skills, outside this app's root: allow serving them and watch them
const SKILLS = fileURLToPath(new URL('../.claude/skills', import.meta.url));

const watchSkills = {
  name: 'watch-skills',
  configureServer(server) {
    server.watcher.add(SKILLS);
  },
};

export default defineConfig({
  plugins: [react(), watchSkills],
  server: { port: 5180, fs: { allow: ['..'] } },
});

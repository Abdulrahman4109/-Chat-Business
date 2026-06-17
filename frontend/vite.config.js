import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/chat': 'http://localhost:8001',
      '/history': 'http://localhost:8001',
      '/health': 'http://localhost:8001',
      '/analyze': 'http://localhost:8001',
      '/calculate': 'http://localhost:8001',
      '/mujarrad': 'http://localhost:8001',
    },
  },
});

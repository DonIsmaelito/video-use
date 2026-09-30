import { defineConfig, loadEnv } from "vite";

// Keep InsForge refresh cookies on the Studio origin, including local development.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd());
  return {
    server: {
      proxy: {
        "/api/auth": { target: env.VITE_INSFORGE_URL, changeOrigin: true },
      },
    },
  };
});

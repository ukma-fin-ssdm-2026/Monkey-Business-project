/**
 * Інструмент: Claude
 * Застосування: Конфігурація Vite-dev-сервера — проксі /v1 та /health на
 * бекенд, щоб обійти відсутній CORSMiddleware у src/api/main.py без
 * жодної зміни бекенду.
 * Верифікація: `npm run dev` піднімає сервер на :5173; `npm run build`
 * пройдено без помилок у цій сесії (бекенд окремо не піднімався).
 */

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Бекенд (src/api/main.py) не підключає CORSMiddleware, тож прямі запити
// з dev-сервера (інший origin) впадуть у CORS. Проксі вирішує це без
// жодних змін на бекенді: у dev фронтенд звертається на свій origin
// (/v1/..., /health), а Vite перенаправляє запит на API.
const API_TARGET = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:3000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": { target: API_TARGET, changeOrigin: true },
      "/health": { target: API_TARGET, changeOrigin: true },
    },
  },
});

/**
 * ## Використання ШІ
 * - **Інструмент:** Codex.
 * - **Застосування:** налаштування Vitest і jsdom для тестів React-компонента.
 * - **Верифікація:** автор переглянув конфігурацію та перевірив результати тестів.
 */
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.tsx"],
    clearMocks: true,
  },
});

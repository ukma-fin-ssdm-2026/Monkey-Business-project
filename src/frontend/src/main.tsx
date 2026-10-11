/**
 * Інструмент: Claude
 * Застосування: Точка входу React-застосунку (Vite + createRoot).
 * Верифікація: Перевірено типи й продакшн-білд (vite build).
 */

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);

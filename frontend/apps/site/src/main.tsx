import "./styles.css";

import { applyLanguage } from "@frutti/i18n";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";

// The site speaks French; Arabic comes with the rest of the apps (P3-T09).
applyLanguage("fr");

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

import "./styles.css";

import { applyLanguage, deviceLanguage } from "@frutti/i18n";
import { initTheme } from "@frutti/ui";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { registerServiceWorker } from "./offline";

initTheme();
// The login screen speaks the language last used on this phone.
applyLanguage(deviceLanguage() ?? "fr");
registerServiceWorker();

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

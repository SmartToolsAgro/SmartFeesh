import "./styles.css";

import { applyLanguage, deviceLanguage } from "@frutti/i18n";
import { initMonitoring, reactErrorHandlers } from "@frutti/monitoring";
import { initTheme } from "@frutti/ui";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { registerServiceWorker } from "./offline";

// Errors go to Sentry only when the build has a DSN (D-140); otherwise nothing is sent.
initMonitoring("truck", import.meta.env);
initTheme();
// The login screen speaks the language last used on this phone.
applyLanguage(deviceLanguage() ?? "fr");
registerServiceWorker();

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

createRoot(root, reactErrorHandlers).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

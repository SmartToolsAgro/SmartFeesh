import "./styles.css";

import { initMonitoring, reactErrorHandlers } from "@frutti/monitoring";
import { initTheme } from "@frutti/ui";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";

// Errors go to Sentry only when the build has a DSN (D-140); otherwise nothing is sent.
initMonitoring("admin", import.meta.env);
initTheme();

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

createRoot(root, reactErrorHandlers).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

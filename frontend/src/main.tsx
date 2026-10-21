import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "./App";
import "./index.css";
import { followDeviceTheme } from "./lib/theme";

// index.html set the theme before paint; this keeps "Match my device" live.
followDeviceTheme();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Installable, and so offered in a phone's share sheet (Sprint 097). Production only,
// and only where the browser allows it at all: a secure context, which the exposure
// rule already requires off the LAN.
if (
  import.meta.env.PROD &&
  "serviceWorker" in navigator &&
  window.isSecureContext
) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js");
  });
}

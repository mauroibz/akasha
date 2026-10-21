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

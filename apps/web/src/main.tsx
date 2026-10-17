import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/bricolage-grotesque/opsz.css";
import "@fontsource-variable/figtree/wght.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/layout.css";
import "./styles/components.css";
import "./styles/charts.css";
import "./styles/pages.css";
import "./styles/landing.css";
import "./styles/print.css";
import { applyStored } from "./lib/theme";
import App from "./App";

applyStored();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

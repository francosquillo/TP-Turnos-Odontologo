import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles/tokens.css";
import "./styles/lista-espera.css";
import "./styles/odontograma.css";

const raiz = document.getElementById("root");
if (raiz === null) throw new Error("Falta #root en index.html");

createRoot(raiz).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

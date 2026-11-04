import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles/tokens.css";
import "./styles/layout.css";
import "./styles/components.css";
import "./styles/lista-espera.css";
import "./styles/odontograma.css";
import "./styles/presupuestos.css";
import "./styles/cuenta-corriente.css";
import "./styles/caja.css";
import "./styles/liquidaciones.css";
import "./styles/seguridad.css";

const raiz = document.getElementById("root");
if (raiz === null) throw new Error("Falta #root en index.html");

createRoot(raiz).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

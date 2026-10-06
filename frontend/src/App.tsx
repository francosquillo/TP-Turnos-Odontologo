import { useState } from "react";
import { AuthProveedor } from "./shared/auth-context";
import { Confirmar } from "./pages/Confirmar";
import { Reservas } from "./pages/Reservas";
import { Seguridad } from "./pages/Seguridad";

type Pagina = "reservas" | "confirmar" | "seguridad";

export function App(): JSX.Element {
  const [pagina, setPagina] = useState<Pagina>("reservas");

  return (
    <AuthProveedor>
      <nav>
        <button type="button" onClick={(): void => setPagina("reservas")}>
          Reservar
        </button>
        <button type="button" onClick={(): void => setPagina("confirmar")}>
          Confirmar
        </button>
        <button type="button" onClick={(): void => setPagina("seguridad")}>
          Seguridad
        </button>
      </nav>
      <main>
        {pagina === "reservas" && <Reservas />}
        {pagina === "confirmar" && <Confirmar />}
        {pagina === "seguridad" && <Seguridad />}
      </main>
    </AuthProveedor>
  );
}

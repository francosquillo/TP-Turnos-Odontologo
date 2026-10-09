import { useState } from "react";
import { AuthProveedor, useAuth } from "./shared/auth-context";
import { RequireRole } from "./shared/RequireRole";
import { Confirmar } from "./pages/Confirmar";
import { Login } from "./pages/Login";
import { Reservas } from "./pages/Reservas";
import { Seguridad } from "./pages/Seguridad";

type Pagina = "reservas" | "confirmar" | "seguridad" | "ingresar" | "admin";

function Barra(): JSX.Element {
  const { sesion, cerrarSesion } = useAuth();
  return (
    <div>
      {sesion === null ? (
        <span>Sin sesión</span>
      ) : (
        <span>
          {sesion.email} ({sesion.rol}){" "}
          <button
            type="button"
            onClick={(): void => {
              void cerrarSesion();
            }}
          >
            Cerrar sesión
          </button>
        </span>
      )}
    </div>
  );
}

function PanelAdmin(): JSX.Element {
  return <p>Panel de administración (demo C-03)</p>;
}

export function App(): JSX.Element {
  const [pagina, setPagina] = useState<Pagina>("reservas");

  return (
    <AuthProveedor>
      <Barra />
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
        <button type="button" onClick={(): void => setPagina("ingresar")}>
          Ingresar
        </button>
        <button type="button" onClick={(): void => setPagina("admin")}>
          Admin
        </button>
      </nav>
      <main>
        {pagina === "reservas" && <Reservas />}
        {pagina === "confirmar" && <Confirmar />}
        {pagina === "seguridad" && <Seguridad />}
        {pagina === "ingresar" && <Login />}
        {pagina === "admin" && (
          <RequireRole roles={["admin"]} alternativa={<Login />}>
            <PanelAdmin />
          </RequireRole>
        )}
      </main>
    </AuthProveedor>
  );
}

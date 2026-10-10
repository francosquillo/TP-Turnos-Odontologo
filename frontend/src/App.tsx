import { useState } from "react";
import { AuthProveedor, useAuth } from "./shared/auth-context";
import { RequireRole } from "./shared/RequireRole";
import { AgendaPage } from "./features/agenda/AgendaPage";
import { Confirmar } from "./pages/Confirmar";
import { Inicio } from "./pages/Inicio";
import { Login } from "./pages/Login";
import { Reservas } from "./pages/Reservas";
import { Seguridad } from "./pages/Seguridad";

type Pagina = "inicio" | "reservas" | "agenda" | "confirmar" | "seguridad" | "ingresar" | "admin";

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
  const [pagina, setPagina] = useState<Pagina>("inicio");
  const [tokenConfirmar, setTokenConfirmar] = useState<string>("");

  function irAPagina(destino: string): void {
    if (destino === "reservas" || destino === "seguridad" || destino === "inicio") {
      setPagina(destino);
    }
  }

  return (
    <AuthProveedor>
      <Barra />
      <nav>
        <button type="button" onClick={(): void => setPagina("inicio")}>
          Inicio
        </button>
        <button type="button" onClick={(): void => setPagina("reservas")}>
          Reservar
        </button>
        <button type="button" onClick={(): void => setPagina("agenda")}>
          Agenda
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
        {pagina === "inicio" && <Inicio alNavegar={irAPagina} />}
        {pagina === "reservas" && (
          <Reservas
            alConfirmar={(token: string): void => {
              setTokenConfirmar(token);
              setPagina("confirmar");
            }}
          />
        )}
        {pagina === "agenda" && (
          <RequireRole
            roles={["admin", "secretaria", "odontologo"]}
            alternativa={<Login />}
          >
            <AgendaPage />
          </RequireRole>
        )}
        {pagina === "confirmar" && <Confirmar token={tokenConfirmar} />}
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

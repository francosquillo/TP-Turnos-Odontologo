import { useState } from "react";
import { AuthProveedor, useAuth } from "./shared/auth-context";
import { RequireRole } from "./shared/RequireRole";
import { AgendaPage } from "./features/agenda/AgendaPage";
import { ListaEsperaPage } from "./features/lista-espera/ListaEsperaPage";
import { Confirmar } from "./pages/Confirmar";
import { Inicio } from "./pages/Inicio";
import { Login } from "./pages/Login";
import { OfertaEspera } from "./pages/OfertaEspera";
import { Reservas } from "./pages/Reservas";
import { Seguridad } from "./pages/Seguridad";

type Pagina = "inicio" | "reservas" | "agenda" | "espera" | "oferta-espera" | "confirmar" | "seguridad" | "ingresar" | "admin";

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

const RUTA_OFERTA = /^\/lista-espera\/([^/]+)\/?$/;

/** Token de la ruta publica `/lista-espera/:token` ("" si la URL es otra). */
function tokenDeRuta(): string {
  const coincide = RUTA_OFERTA.exec(window.location.pathname);
  return coincide?.[1] === undefined ? "" : decodeURIComponent(coincide[1]);
}

export function App(): JSX.Element {
  const [tokenOferta] = useState<string>(tokenDeRuta);
  const [pagina, setPagina] = useState<Pagina>(tokenOferta === "" ? "inicio" : "oferta-espera");
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
        <button type="button" onClick={(): void => setPagina("espera")}>
          Lista de espera
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
        {pagina === "espera" && (
          <RequireRole roles={["admin", "secretaria"]} alternativa={<Login />}>
            <ListaEsperaPage />
          </RequireRole>
        )}
        {pagina === "oferta-espera" && <OfertaEspera token={tokenOferta} />}
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

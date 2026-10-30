import { lazy, Suspense, useState } from "react";
import { AuthProveedor, useAuth } from "./shared/auth-context";
import { RequireRole } from "./shared/RequireRole";
import { AgendaPage } from "./features/agenda/AgendaPage";
import type { TurnoAgenda } from "./features/agenda/tipos";
import { ListaEsperaPage } from "./features/lista-espera/ListaEsperaPage";
import { Confirmar } from "./pages/Confirmar";
import { Inicio } from "./pages/Inicio";
import { Login } from "./pages/Login";
import { OfertaEspera } from "./pages/OfertaEspera";
import { Reservas } from "./pages/Reservas";
import { Seguridad } from "./pages/Seguridad";

type Pagina = "inicio" | "reservas" | "agenda" | "odontograma" | "espera" | "oferta-espera" | "confirmar" | "seguridad" | "ingresar" | "admin";

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

// C-08: el odontograma se carga bajo demanda (no pesa en la landing publica).
const OdontogramaPage = lazy(() =>
  import("./features/odontograma/OdontogramaPage").then((m) => ({ default: m.OdontogramaPage })),
);

interface PacienteAbierto {
  id: number;
  nombre: string;
}

/** Agenda con acceso al odontograma solo para odontologo y secretaria (el admin no ve PHI). */
function AgendaRuta({ alAbrir }: { alAbrir: (turno: TurnoAgenda) => void }): JSX.Element {
  const { sesion } = useAuth();
  const habilita = sesion?.rol === "odontologo" || sesion?.rol === "secretaria";
  return <AgendaPage {...(habilita ? { alAbrirOdontograma: alAbrir } : {})} />;
}

function OdontogramaRuta({ paciente, alVolver }: { paciente: PacienteAbierto; alVolver: () => void }): JSX.Element {
  const { sesion } = useAuth();
  const rol = sesion?.rol === "odontologo" ? "odontologo" : "secretaria";
  return (
    <Suspense fallback={<p>Cargando odontograma…</p>}>
      <OdontogramaPage pacienteId={paciente.id} pacienteNombre={paciente.nombre} rol={rol} alVolver={alVolver} />
    </Suspense>
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
  const [paciente, setPaciente] = useState<PacienteAbierto | null>(null);

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
            <AgendaRuta
              alAbrir={(turno: TurnoAgenda): void => {
                setPaciente({
                  id: turno.paciente_id,
                  nombre: turno.paciente_nombre ?? `Paciente ${turno.paciente_id}`,
                });
                setPagina("odontograma");
              }}
            />
          </RequireRole>
        )}
        {pagina === "odontograma" && paciente !== null && (
          <RequireRole roles={["secretaria", "odontologo"]} alternativa={<Login />}>
            <OdontogramaRuta paciente={paciente} alVolver={(): void => setPagina("agenda")} />
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

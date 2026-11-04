import { lazy, Suspense, useState } from "react";
import { AuthProveedor, useAuth } from "./shared/auth-context";
import { RequireRole } from "./shared/RequireRole";
import { AppHeader } from "./shared/layout/AppHeader";
import type { Pagina } from "./shared/layout/AppHeader";
import { AgendaPage } from "./features/agenda/AgendaPage";
import type { TurnoAgenda } from "./features/agenda/tipos";
import { ListaEsperaPage } from "./features/lista-espera/ListaEsperaPage";
import { Confirmar } from "./pages/Confirmar";
import { Inicio } from "./pages/Inicio";
import { Login } from "./pages/Login";
import { OfertaEspera } from "./pages/OfertaEspera";
import { Reservas } from "./pages/Reservas";
import { Seguridad } from "./pages/Seguridad";

// C-08: el odontograma se carga bajo demanda (no pesa en la landing publica).
const OdontogramaPage = lazy(() =>
  import("./features/odontograma/OdontogramaPage").then((m) => ({ default: m.OdontogramaPage })),
);

// C-09: la cuenta corriente tambien se carga bajo demanda.
const CuentaPage = lazy(() =>
  import("./features/cuenta-corriente/CuentaPage").then((m) => ({ default: m.CuentaPage })),
);

// C-10: la caja y los recibos tambien se cargan bajo demanda.
const CajaPage = lazy(() =>
  import("./features/caja/CajaPage").then((m) => ({ default: m.CajaPage })),
);

// C-11: las liquidaciones a obras sociales tambien se cargan bajo demanda.
const LiquidacionesPage = lazy(() =>
  import("./features/liquidaciones/LiquidacionesPage").then((m) => ({ default: m.LiquidacionesPage })),
);

interface PacienteAbierto {
  id: number;
  nombre: string;
}

interface AgendaRutaProps {
  alAbrir: (turno: TurnoAgenda) => void;
  alAbrirCuenta: (turno: TurnoAgenda) => void;
}

/** Agenda con acceso al odontograma para odontologo y secretaria (el admin no ve PHI) y a la
 * cuenta corriente para secretaria y admin (el odontologo no la ve, D-15). */
function AgendaRuta({ alAbrir, alAbrirCuenta }: AgendaRutaProps): JSX.Element {
  const { sesion } = useAuth();
  const habilita = sesion?.rol === "odontologo" || sesion?.rol === "secretaria";
  const habilitaCuenta = sesion?.rol === "secretaria" || sesion?.rol === "admin";
  return (
    <AgendaPage
      {...(habilita ? { alAbrirOdontograma: alAbrir } : {})}
      {...(habilitaCuenta ? { alAbrirCuenta } : {})}
    />
  );
}

function CuentaRuta({ paciente, alVolver }: { paciente: PacienteAbierto; alVolver: () => void }): JSX.Element {
  const { sesion } = useAuth();
  const rol = sesion?.rol === "admin" ? "admin" : "secretaria";
  return (
    <Suspense fallback={<p>Cargando cuenta corriente…</p>}>
      <CuentaPage pacienteId={paciente.id} pacienteNombre={paciente.nombre} rol={rol} alVolver={alVolver} />
    </Suspense>
  );
}

function CajaRuta(): JSX.Element {
  const { sesion } = useAuth();
  const rol = sesion?.rol === "admin" ? "admin" : "secretaria";
  return (
    <Suspense fallback={<p>Cargando caja…</p>}>
      <CajaPage rol={rol} />
    </Suspense>
  );
}

/** El admin opera las liquidaciones; el odontologo las ve en modo lectura (solo sus filas). */
function LiquidacionesRuta(): JSX.Element {
  const { sesion } = useAuth();
  const rol = sesion?.rol === "odontologo" ? "odontologo" : "admin";
  return (
    <Suspense fallback={<p>Cargando liquidaciones…</p>}>
      <LiquidacionesPage rol={rol} />
    </Suspense>
  );
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

// C-12: el panel admin (usuarios, exportacion) tambien se carga bajo demanda.
const PanelAdminPage = lazy(() =>
  import("./features/admin/PanelAdmin").then((m) => ({ default: m.PanelAdmin })),
);

function PanelAdmin(): JSX.Element {
  return (
    <Suspense fallback={<p>Cargando panel…</p>}>
      <PanelAdminPage />
    </Suspense>
  );
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
      <div className="app-shell">
        <AppHeader pagina={pagina} alCambiarPagina={(p): void => setPagina(p)} />
        <main className="app-main wrap">
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
              alAbrirCuenta={(turno: TurnoAgenda): void => {
                setPaciente({
                  id: turno.paciente_id,
                  nombre: turno.paciente_nombre ?? `Paciente ${turno.paciente_id}`,
                });
                setPagina("cuenta");
              }}
            />
          </RequireRole>
        )}
        {pagina === "odontograma" && paciente !== null && (
          <RequireRole roles={["secretaria", "odontologo"]} alternativa={<Login />}>
            <OdontogramaRuta paciente={paciente} alVolver={(): void => setPagina("agenda")} />
          </RequireRole>
        )}
        {pagina === "cuenta" && paciente !== null && (
          <RequireRole roles={["secretaria", "admin"]} alternativa={<Login />}>
            <CuentaRuta paciente={paciente} alVolver={(): void => setPagina("agenda")} />
          </RequireRole>
        )}
        {pagina === "caja" && (
          <RequireRole roles={["secretaria", "admin"]} alternativa={<Login />}>
            <CajaRuta />
          </RequireRole>
        )}
        {pagina === "liquidaciones" && (
          <RequireRole roles={["admin", "odontologo"]} alternativa={<Login />}>
            <LiquidacionesRuta />
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
      </div>
    </AuthProveedor>
  );
}

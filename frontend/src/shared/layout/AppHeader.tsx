import { useAuth } from "../auth-context";
import { useTheme } from "../theme/useTheme";

export type Pagina =
  | "inicio"
  | "reservas"
  | "agenda"
  | "odontograma"
  | "cuenta"
  | "caja"
  | "liquidaciones"
  | "espera"
  | "oferta-espera"
  | "confirmar"
  | "seguridad"
  | "ingresar"
  | "admin";

interface Props {
  pagina: Pagina;
  alCambiarPagina: (destino: Pagina) => void;
}

export function AppHeader({ pagina, alCambiarPagina }: Props): JSX.Element {
  const { sesion, cerrarSesion } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="topbar">
      <div className="topbar-content">
        <div
          className="brand"
          onClick={(): void => alCambiarPagina("inicio")}
          role="button"
          tabIndex={0}
          onKeyDown={(e): void => {
            if (e.key === "Enter" || e.key === " ") alCambiarPagina("inicio");
          }}
        >
          <span className="brand-icon" aria-hidden="true">
            🦷
          </span>
          <span className="brand-name">Turnos Odontólogo</span>
        </div>

        <div className="user-status" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
            title={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
            style={{ fontSize: "1.1rem", padding: "var(--space-1) var(--space-2)" }}
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
          {sesion === null ? (
            <span>Sin sesión</span>
          ) : (
            <div className="row" style={{ gap: "var(--space-2)" }}>
              <span>
                {sesion.email} ({sesion.rol})
              </span>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={(): void => {
                  void cerrarSesion();
                }}
              >
                Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </div>

      <nav className="main-nav" aria-label="Navegación principal">
        <button
          type="button"
          className="nav-tab"
          aria-current={pagina === "inicio" ? "page" : undefined}
          onClick={(): void => alCambiarPagina("inicio")}
        >
          Inicio
        </button>
        <button
          type="button"
          className="nav-tab"
          aria-current={pagina === "reservas" ? "page" : undefined}
          onClick={(): void => alCambiarPagina("reservas")}
        >
          Reservar
        </button>
        <button
          type="button"
          className="nav-tab"
          aria-current={pagina === "agenda" ? "page" : undefined}
          onClick={(): void => alCambiarPagina("agenda")}
        >
          Agenda
        </button>
        <button
          type="button"
          className="nav-tab"
          aria-current={pagina === "caja" ? "page" : undefined}
          onClick={(): void => alCambiarPagina("caja")}
        >
          Caja
        </button>
        <button
          type="button"
          className="nav-tab"
          aria-current={pagina === "liquidaciones" ? "page" : undefined}
          onClick={(): void => alCambiarPagina("liquidaciones")}
        >
          Liquidaciones
        </button>
        <button
          type="button"
          className="nav-tab"
          aria-current={pagina === "espera" ? "page" : undefined}
          onClick={(): void => alCambiarPagina("espera")}
        >
          Lista de espera
        </button>
        <button
          type="button"
          className="nav-tab"
          aria-current={pagina === "confirmar" ? "page" : undefined}
          onClick={(): void => alCambiarPagina("confirmar")}
        >
          Confirmar
        </button>
        <button
          type="button"
          className="nav-tab"
          aria-current={pagina === "seguridad" ? "page" : undefined}
          onClick={(): void => alCambiarPagina("seguridad")}
        >
          Seguridad
        </button>
        <button
          type="button"
          className="nav-tab"
          aria-current={pagina === "ingresar" ? "page" : undefined}
          onClick={(): void => alCambiarPagina("ingresar")}
        >
          Ingresar
        </button>
        <button
          type="button"
          className="nav-tab"
          aria-current={pagina === "admin" ? "page" : undefined}
          onClick={(): void => alCambiarPagina("admin")}
        >
          Admin
        </button>
      </nav>
    </header>
  );
}

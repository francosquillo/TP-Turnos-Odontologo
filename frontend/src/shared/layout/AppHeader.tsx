import { useState } from "react";
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

interface ItemNavegacion {
  id: Pagina;
  label: string;
  icon: string;
}

const ITEMS: readonly ItemNavegacion[] = [
  { id: "inicio", label: "Inicio", icon: "🏠" },
  { id: "reservas", label: "Reservar", icon: "📅" },
  { id: "agenda", label: "Agenda", icon: "🗓️" },
  { id: "caja", label: "Caja", icon: "💰" },
  { id: "liquidaciones", label: "Liquidaciones", icon: "📑" },
  { id: "espera", label: "Lista de espera", icon: "⏳" },
  { id: "confirmar", label: "Confirmar", icon: "✅" },
  { id: "seguridad", label: "Seguridad", icon: "🛡️" },
  { id: "ingresar", label: "Ingresar", icon: "🔑" },
  { id: "admin", label: "Admin", icon: "⚙️" },
];

export function AppHeader({ pagina, alCambiarPagina }: Props): JSX.Element {
  const { sesion, cerrarSesion } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const [colapsada, setColapsada] = useState<boolean>(() => {
    try {
      return localStorage.getItem("sidebar-colapsada") === "true";
    } catch {
      return false;
    }
  });
  const [movilAbierta, setMovilAbierta] = useState<boolean>(false);

  const alternarColapso = (): void => {
    setColapsada((prev) => {
      const sig = !prev;
      try {
        localStorage.setItem("sidebar-colapsada", String(sig));
      } catch {
        // Ignora restricciones de storage
      }
      return sig;
    });
  };

  return (
    <>
      {/* Barra superior visible en móviles para abrir el menú lateral */}
      <header className="mobile-topbar" aria-label="Barra móvil">
        <button
          type="button"
          className="sidebar-collapse-btn"
          aria-label="Abrir menú"
          onClick={(): void => setMovilAbierta(true)}
        >
          ☰
        </button>
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
        <button
          type="button"
          className="btn btn-ghost btn-sm theme-toggle-btn"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
          title={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
        >
          {theme === "dark" ? "☀️" : "🌙"}
        </button>
      </header>

      {/* Backdrop para cerrar la barra en móvil */}
      {movilAbierta && (
        <div
          className="sidebar-backdrop"
          role="presentation"
          onClick={(): void => setMovilAbierta(false)}
        />
      )}

      {/* Barra lateral principal */}
      <aside
        className={`app-sidebar ${colapsada ? "collapsed" : ""} ${movilAbierta ? "mobile-open" : ""}`}
        aria-label="Barra lateral"
      >
        <div className="sidebar-header">
          <div
            className="brand"
            onClick={(): void => {
              alCambiarPagina("inicio");
              setMovilAbierta(false);
            }}
            role="button"
            tabIndex={0}
            onKeyDown={(e): void => {
              if (e.key === "Enter" || e.key === " ") {
                alCambiarPagina("inicio");
                setMovilAbierta(false);
              }
            }}
          >
            <span className="brand-icon" aria-hidden="true">
              🦷
            </span>
            <span className="brand-name">Turnos Odontólogo</span>
          </div>
          <button
            type="button"
            className="sidebar-collapse-btn desktop-only"
            onClick={alternarColapso}
            aria-label={colapsada ? "Expandir barra lateral" : "Contraer barra lateral"}
            title={colapsada ? "Expandir barra lateral" : "Contraer barra lateral"}
          >
            {colapsada ? "▶" : "◀"}
          </button>
          <button
            type="button"
            className="sidebar-collapse-btn mobile-only"
            onClick={(): void => setMovilAbierta(false)}
            aria-label="Cerrar menú"
          >
            ✕
          </button>
        </div>

        <nav className="main-nav" aria-label="Navegación principal">
          {ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className="nav-tab"
              aria-label={item.label}
              title={item.label}
              aria-current={pagina === item.id ? "page" : undefined}
              onClick={(): void => {
                alCambiarPagina(item.id);
                setMovilAbierta(false);
              }}
            >
              <span className="nav-tab-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span className="nav-tab-label">{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-status">
            {sesion === null ? (
              <span className="user-details">Sin sesión</span>
            ) : (
              <>
                <div className="user-details">
                  <span className="user-email" title={sesion.email}>
                    {sesion.email}
                  </span>
                  <span className="user-role-badge">
                    {sesion.rol}
                  </span>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    style={{ alignSelf: "flex-start", marginTop: "var(--space-1)" }}
                    onClick={(): void => {
                      void cerrarSesion();
                      setMovilAbierta(false);
                    }}
                  >
                    Cerrar sesión
                  </button>
                </div>
                {colapsada && (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm sidebar-collapsed-logout"
                    title={`Cerrar sesión (${sesion.email})`}
                    aria-label="Cerrar sesión"
                    onClick={(): void => {
                      void cerrarSesion();
                      setMovilAbierta(false);
                    }}
                  >
                    🚪
                  </button>
                )}
              </>
            )}
          </div>
          <div className="sidebar-footer-controls">
            <span className="nav-tab-label" style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              Tema
            </span>
            <button
              type="button"
              className="btn btn-ghost btn-sm theme-toggle-btn"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
              title={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
            >
              {theme === "dark" ? "☀️" : "🌙"}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

export const AppSidebar = AppHeader;

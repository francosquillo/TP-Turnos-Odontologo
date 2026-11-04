import { useState } from "react";
import { ExportacionTotal } from "./ExportacionTotal";
import { ImportarPacientes } from "./ImportarPacientes";
import { UsuariosPage } from "./UsuariosPage";

type SubSeccion = "usuarios" | "importar" | "exportar";

/** Panel de administracion (solo admin): usuarios, importacion de pacientes y exportacion total. */
export function PanelAdmin(): JSX.Element {
  const [subSeccion, setSubSeccion] = useState<SubSeccion>("usuarios");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <div className="card row" style={{ justifyContent: "space-between", padding: "var(--space-3)" }}>
        <h2 style={{ margin: 0, fontSize: "var(--text-lg)", color: "var(--color-primary)" }}>
          Panel de Administración
        </h2>
        <div className="row" style={{ gap: "var(--space-2)" }}>
          <button
            type="button"
            className={`btn ${subSeccion === "usuarios" ? "btn-primary" : "btn-secondary"} btn-sm`}
            onClick={(): void => setSubSeccion("usuarios")}
          >
            Usuarios
          </button>
          <button
            type="button"
            className={`btn ${subSeccion === "importar" ? "btn-primary" : "btn-secondary"} btn-sm`}
            onClick={(): void => setSubSeccion("importar")}
          >
            Importar Pacientes
          </button>
          <button
            type="button"
            className={`btn ${subSeccion === "exportar" ? "btn-primary" : "btn-secondary"} btn-sm`}
            onClick={(): void => setSubSeccion("exportar")}
          >
            Exportar Datos
          </button>
        </div>
      </div>

      {subSeccion === "usuarios" && (
        <div className="card">
          <UsuariosPage />
        </div>
      )}

      {subSeccion === "importar" && (
        <div className="card">
          <ImportarPacientes />
        </div>
      )}

      {subSeccion === "exportar" && (
        <div className="card">
          <ExportacionTotal />
        </div>
      )}
    </div>
  );
}

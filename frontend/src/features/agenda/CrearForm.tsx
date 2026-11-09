import { useState } from "react";
import type { CrearTurnoDatos } from "./api";

interface Props {
  alCrear: (datos: CrearTurnoDatos) => void;
}

export function CrearForm({ alCrear }: Props): JSX.Element {
  const [pacienteId, setPacienteId] = useState<string>("1");
  const [profesionalId, setProfesionalId] = useState<string>("1");
  const [sillonId, setSillonId] = useState<string>("1");
  const [inicio, setInicio] = useState<string>("");
  const [fin, setFin] = useState<string>("");

  return (
    <form
      aria-label="Crear turno"
      className="card"
      onSubmit={(e): void => {
        e.preventDefault();
        if (inicio === "" || fin === "") return;
        alCrear({
          paciente_id: Number(pacienteId),
          profesional_id: Number(profesionalId),
          sillon_id: Number(sillonId),
          inicio: new Date(inicio).toISOString(),
          fin: new Date(fin).toISOString(),
        });
      }}
    >
      <h3 style={{ marginBottom: "var(--space-3)", color: "var(--color-primary)" }}>
        Nuevo turno manual
      </h3>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: "var(--space-3)",
          alignItems: "end",
        }}
      >
        <div className="field" style={{ margin: 0 }}>
          <label>
            Paciente
            <input
              aria-label="Paciente"
              className="input"
              value={pacienteId}
              onChange={(e): void => setPacienteId(e.target.value)}
            />
          </label>
        </div>
        <div className="field" style={{ margin: 0 }}>
          <label>
            Profesional
            <input
              aria-label="Profesional"
              className="input"
              value={profesionalId}
              onChange={(e): void => setProfesionalId(e.target.value)}
            />
          </label>
        </div>
        <div className="field" style={{ margin: 0 }}>
          <label>
            Sillón
            <input
              aria-label="Sillón"
              className="input"
              value={sillonId}
              onChange={(e): void => setSillonId(e.target.value)}
            />
          </label>
        </div>
        <div className="field" style={{ margin: 0 }}>
          <label htmlFor="crear-inicio">Inicio</label>
          <input
            id="crear-inicio"
            className="input"
            type="datetime-local"
            value={inicio}
            onChange={(e): void => setInicio(e.target.value)}
          />
        </div>
        <div className="field" style={{ margin: 0 }}>
          <label htmlFor="crear-fin">Fin</label>
          <input
            id="crear-fin"
            className="input"
            type="datetime-local"
            value={fin}
            onChange={(e): void => setFin(e.target.value)}
          />
        </div>
        <div style={{ display: "flex", alignItems: "flex-end" }}>
          <button type="submit" className="btn btn-primary" style={{ width: "100%" }}>
            Crear turno
          </button>
        </div>
      </div>
    </form>
  );
}

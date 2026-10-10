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
      <label>
        Paciente
        <input
          aria-label="Paciente"
          value={pacienteId}
          onChange={(e): void => setPacienteId(e.target.value)}
        />
      </label>
      <label>
        Profesional
        <input
          aria-label="Profesional"
          value={profesionalId}
          onChange={(e): void => setProfesionalId(e.target.value)}
        />
      </label>
      <label>
        Sillón
        <input
          aria-label="Sillón"
          value={sillonId}
          onChange={(e): void => setSillonId(e.target.value)}
        />
      </label>
      <label htmlFor="crear-inicio">Inicio</label>
      <input
        id="crear-inicio"
        type="datetime-local"
        value={inicio}
        onChange={(e): void => setInicio(e.target.value)}
      />
      <label htmlFor="crear-fin">Fin</label>
      <input
        id="crear-fin"
        type="datetime-local"
        value={fin}
        onChange={(e): void => setFin(e.target.value)}
      />
      <button type="submit">Crear turno</button>
    </form>
  );
}

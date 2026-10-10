import type { DragEvent } from "react";

interface Props {
  nuevoHorario: string;
  alCambiarHorario: (valor: string) => void;
  alSoltar: (e: DragEvent) => void;
}

/** Zona de drop para reprogramar por drag (D-08: rollback ante 409). */
export function ReprogramarZona({
  nuevoHorario,
  alCambiarHorario,
  alSoltar,
}: Props): JSX.Element {
  return (
    <section
      data-testid="zona-reprogramar"
      onDragOver={(e: DragEvent): void => e.preventDefault()}
      onDrop={alSoltar}
    >
      <h3>Reprogramar por arrastre</h3>
      <p>Arrastrá un turno hasta acá para moverlo al nuevo horario.</p>
      <label htmlFor="nuevo-horario">Nuevo horario</label>
      <input
        id="nuevo-horario"
        type="datetime-local"
        value={nuevoHorario}
        onChange={(e): void => alCambiarHorario(e.target.value)}
      />
    </section>
  );
}

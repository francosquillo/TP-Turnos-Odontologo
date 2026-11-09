import { useState } from "react";
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
  const [arrastrandoSobre, setArrastrandoSobre] = useState<boolean>(false);

  return (
    <section
      data-testid="zona-reprogramar"
      className="card"
      style={{
        borderStyle: "dashed",
        borderWidth: "2px",
        borderColor: arrastrandoSobre ? "var(--color-primary)" : "var(--color-border-strong)",
        background: arrastrandoSobre ? "var(--color-primary-soft)" : "var(--color-surface-alt)",
        transition: "background-color var(--motion-fast) var(--ease-out), border-color var(--motion-fast) var(--ease-out)",
      }}
      onDragOver={(e: DragEvent): void => {
        e.preventDefault();
        if (!arrastrandoSobre) setArrastrandoSobre(true);
      }}
      onDragLeave={(): void => setArrastrandoSobre(false)}
      onDrop={(e: DragEvent): void => {
        setArrastrandoSobre(false);
        alSoltar(e);
      }}
    >
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-end", gap: "var(--space-4)" }}>
        <div style={{ flex: "1 1 260px" }}>
          <h3 style={{ marginBottom: "var(--space-1)", color: "var(--color-primary)" }}>
            ⇄ Reprogramar por arrastre
          </h3>
          <p className="muted" style={{ margin: 0 }}>
            Elegí primero la nueva fecha/hora y arrastrá una tarjeta de turno hasta esta zona para moverlo.
          </p>
        </div>
        <div className="field" style={{ margin: 0, flex: "0 1 260px", minWidth: "220px" }}>
          <label htmlFor="nuevo-horario">Nuevo horario</label>
          <input
            id="nuevo-horario"
            className="input"
            type="datetime-local"
            value={nuevoHorario}
            onChange={(e): void => alCambiarHorario(e.target.value)}
          />
        </div>
      </div>
    </section>
  );
}

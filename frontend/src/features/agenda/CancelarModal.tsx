import { useState } from "react";
import type { TurnoAgenda } from "./tipos";

interface Props {
  turno: TurnoAgenda;
  alCerrar: () => void;
  alConfirmar: (motivo: string) => void;
}

export function CancelarModal({ turno, alCerrar, alConfirmar }: Props): JSX.Element {
  const [motivo, setMotivo] = useState<string>("");
  const valido = motivo.trim().length > 0;

  return (
    <div className="dialog-backdrop" role="presentation">
      <div className="dialog" role="dialog" aria-label="Cancelar turno">
        <h3 style={{ color: "var(--color-danger-text)", marginTop: 0 }}>
          Cancelar turno de {turno.paciente_nombre ?? turno.paciente_id}
        </h3>
        <p className="muted">
          Esta acción liberará el espacio en la agenda y registrará la cancelación con motivo obligatorio.
        </p>
        <div className="field">
          <label htmlFor="motivo-cancelacion">Motivo de cancelación</label>
          <textarea
            id="motivo-cancelacion"
            className="input"
            rows={3}
            placeholder="Ingresá el motivo (paciente avisó, imprevisto, etc.)"
            value={motivo}
            onChange={(e): void => setMotivo(e.target.value)}
          />
        </div>
        <div className="row" style={{ justifyContent: "flex-end", gap: "var(--space-2)" }}>
          <button type="button" className="btn btn-secondary" onClick={alCerrar}>
            Volver
          </button>
          <button
            type="button"
            className="btn btn-danger"
            disabled={!valido}
            onClick={(): void => {
              if (valido) alConfirmar(motivo.trim());
            }}
          >
            Confirmar cancelación
          </button>
        </div>
      </div>
    </div>
  );
}

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
    <div role="dialog" aria-label="Cancelar turno">
      <h3>Cancelar turno de {turno.paciente_nombre ?? turno.paciente_id}</h3>
      <label htmlFor="motivo-cancelacion">Motivo de cancelación</label>
      <textarea
        id="motivo-cancelacion"
        value={motivo}
        onChange={(e): void => setMotivo(e.target.value)}
      />
      <div>
        <button type="button" onClick={alCerrar}>
          Volver
        </button>
        <button
          type="button"
          disabled={!valido}
          onClick={(): void => {
            if (valido) alConfirmar(motivo.trim());
          }}
        >
          Confirmar cancelación
        </button>
      </div>
    </div>
  );
}

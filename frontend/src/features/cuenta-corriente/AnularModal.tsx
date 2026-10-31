import { useState } from "react";
import { ApiError } from "../../shared/api-client";
import { MotivoForm } from "../../shared/MotivoForm";
import { formatearMoneda } from "../../shared/moneda";
import type { Movimiento } from "./tipos";

interface Props {
  movimiento: Movimiento;
  alCerrar: () => void;
  /** Debe resolver si la anulacion se hizo; un rechazo mantiene el dialogo abierto. */
  alConfirmar: (motivo: string) => Promise<void>;
}

/** Dialogo de anulacion de un cargo (como `CancelarModal`, con `role="dialog"`). */
export function AnularModal({ movimiento, alCerrar, alConfirmar }: Props): JSX.Element {
  const [error, setError] = useState<string | null>(null);

  async function confirmar(motivo: string): Promise<void> {
    setError(null);
    try {
      await alConfirmar(motivo);
    } catch (fallo) {
      setError(fallo instanceof ApiError ? fallo.message : "No se pudo anular el cargo");
    }
  }

  return (
    <div role="dialog" aria-label="Anular cargo" className="cuenta-modal">
      <h4>Anular el cargo de {formatearMoneda(movimiento.monto)}</h4>
      <p className="muted">
        Se crea un contramovimiento por el mismo importe. El cargo original se conserva en el historial.
      </p>
      {error !== null && (
        <p role="alert" className="banner banner-error">
          {error}
        </p>
      )}
      <MotivoForm
        idBase={`anular-${movimiento.id}`}
        etiqueta="Motivo de la anulación"
        textoBoton="Confirmar anulación"
        peligro
        alConfirmar={confirmar}
        alCancelar={alCerrar}
      />
    </div>
  );
}

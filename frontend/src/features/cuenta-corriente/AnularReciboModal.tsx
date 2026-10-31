import { useState } from "react";
import { ApiError } from "../../shared/api-client";
import { MotivoForm } from "../../shared/MotivoForm";
import { formatearMoneda } from "../../shared/moneda";

interface Props {
  /** Numero del recibo que se anula (el que ve el paciente). */
  numero: string;
  /** Importe del pago, con signo (texto): se muestra sin signo. */
  monto: string;
  alCerrar: () => void;
  /** Debe resolver si la anulacion se hizo; un rechazo mantiene el dialogo abierto. */
  alConfirmar: (motivo: string) => Promise<void>;
}

/** Dialogo de anulacion de un recibo (admin): contramovimiento en la caja de HOY, con motivo. */
export function AnularReciboModal({ numero, monto, alCerrar, alConfirmar }: Props): JSX.Element {
  const [error, setError] = useState<string | null>(null);

  async function confirmar(motivo: string): Promise<void> {
    setError(null);
    try {
      await alConfirmar(motivo);
    } catch (fallo) {
      setError(fallo instanceof ApiError ? fallo.message : "No se pudo anular el recibo");
    }
  }

  return (
    <div role="dialog" aria-label="Anular recibo" className="cuenta-modal">
      <h4>
        Anular el recibo {numero} por {formatearMoneda(monto.replace(/^-/, ""))}
      </h4>
      <p className="muted">
        La devolución se registra en la caja de hoy y el recibo conserva su número. El pendiente del
        presupuesto vuelve a subir.
      </p>
      {error !== null && (
        <p role="alert" className="banner banner-error">
          {error}
        </p>
      )}
      <MotivoForm
        idBase={`anular-recibo-${numero}`}
        etiqueta="Motivo de la anulación"
        textoBoton="Confirmar anulación"
        peligro
        alConfirmar={confirmar}
        alCancelar={alCerrar}
      />
    </div>
  );
}

import { useState } from "react";
import { ApiError } from "../../shared/api-client";
import { MotivoForm } from "../../shared/MotivoForm";
import { formatearMoneda } from "../../shared/moneda";
import { ETIQUETA_MEDIO } from "./tipos";
import type { Recibo } from "./tipos";

interface Props {
  recibos: Recibo[];
  /** Solo `admin` anula; la secretaria solo consulta. */
  rol: "secretaria" | "admin";
  /** Debe resolver si se anulo; un rechazo mantiene el formulario abierto con el error. */
  alAnular: (reciboId: number, motivo: string) => Promise<void>;
}

/** Recibos del dia: numero, paciente, importe y medio. El anulado se dice con texto y su motivo. */
export function RecibosLista({ recibos, rol, alAnular }: Props): JSX.Element {
  const [abierto, setAbierto] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function confirmar(recibo: Recibo, motivo: string): Promise<void> {
    setError(null);
    try {
      await alAnular(recibo.id, motivo);
      setAbierto(null);
    } catch (fallo) {
      setError(fallo instanceof ApiError ? fallo.message : "No se pudo anular el recibo");
    }
  }

  if (recibos.length === 0) {
    return <p className="muted">No hay recibos emitidos en este día.</p>;
  }

  return (
    <ul className="caja-recibos" aria-label="Recibos del día">
      {recibos.map((r) => (
        <li key={r.id} data-anulado={r.anulado}>
          <span className="titulo">Recibo N° {r.numero}</span>
          <span className="muted">{r.paciente_nombre}</span>
          <span className="pres-importe">{formatearMoneda(r.monto)}</span>
          <span className="muted">{ETIQUETA_MEDIO[r.medio]}</span>
          {r.anulado && <span className="pres-aviso">Anulado</span>}
          {r.anulado && r.motivo_anulacion !== null && (
            <span className="muted">Motivo de la anulación: {r.motivo_anulacion}</span>
          )}
          {rol === "admin" && !r.anulado && (
            <span className="caja-acciones">
              <button
                type="button"
                className="btn btn-danger btn-sm"
                aria-label={`Anular recibo ${r.numero}`}
                onClick={(): void => {
                  setError(null);
                  setAbierto(r.id);
                }}
              >
                Anular
              </button>
            </span>
          )}
          {abierto === r.id && (
            <div className="caja-anulacion">
              {error !== null && (
                <p role="alert" className="banner banner-error">
                  {error}
                </p>
              )}
              <MotivoForm
                idBase={`anular-recibo-${r.id}`}
                etiqueta="Motivo de la anulación"
                textoBoton="Confirmar anulación"
                peligro
                alConfirmar={(motivo): Promise<void> => confirmar(r, motivo)}
                alCancelar={(): void => {
                  setError(null);
                  setAbierto(null);
                }}
              />
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

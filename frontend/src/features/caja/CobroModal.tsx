import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "../../shared/api-client";
import { cobrar } from "./api";
import { ComprobanteRecibo } from "./ComprobanteRecibo";
import { ETIQUETA_MEDIO, MEDIOS, esImporteValido } from "./tipos";
import type { Cobro, Medio } from "./tipos";

interface Props {
  presupuestoId: number;
  /** Texto decimal del pendiente (sugerido como importe; el servidor decide el tope). */
  pendiente: string;
  /** El cobro se registro: el padre refresca saldo y pendientes desde el servidor. */
  alCobrado: () => void;
  /** Cierra el formulario. `refrescar` = true cuando el resultado quedo incierto. */
  alCerrar: (refrescar: boolean) => void;
}

type Fase =
  | { tipo: "editando" }
  | { tipo: "enviando" }
  | { tipo: "incierto" }
  | { tipo: "listo"; cobro: Cobro };

/** Una sola clave por apertura (D-25): se conserva en los reintentos y cambia al reabrir. */
function claveNueva(): string {
  return crypto.randomUUID();
}

/** Un fallo sin respuesta o con 5xx deja el resultado incierto: puede haberse registrado. */
function esIncierto(fallo: unknown): boolean {
  return !(fallo instanceof ApiError) || fallo.httpStatus === 0 || fallo.httpStatus >= 500;
}

export function CobroModal({ presupuestoId, pendiente, alCobrado, alCerrar }: Props): JSX.Element {
  const [clave] = useState<string>(claveNueva);
  const [importe, setImporte] = useState<string>(pendiente);
  const [medio, setMedio] = useState<Medio>("efectivo");
  const [fase, setFase] = useState<Fase>({ tipo: "editando" });
  const [error, setError] = useState<string | null>(null);

  async function enviar(e?: FormEvent): Promise<void> {
    e?.preventDefault();
    if (fase.tipo === "enviando" || fase.tipo === "listo") return;
    const monto = importe.trim();
    if (!esImporteValido(monto)) {
      setError("Ingresá un importe válido mayor a cero, con hasta dos decimales (por ejemplo 400.00).");
      return;
    }
    setError(null);
    setFase({ tipo: "enviando" });
    try {
      const { cobro } = await cobrar({
        presupuesto_id: presupuestoId,
        monto,
        medio,
        clave_idempotencia: clave,
      });
      setFase({ tipo: "listo", cobro });
      alCobrado();
    } catch (fallo) {
      if (esIncierto(fallo)) {
        setError("No sabemos si el cobro se registró. Reintentá con los mismos datos o cerrá y revisá la cuenta.");
        setFase({ tipo: "incierto" });
      } else {
        setError(fallo instanceof ApiError ? fallo.message : "No se pudo registrar el cobro");
        setFase({ tipo: "editando" });
      }
    }
  }

  if (fase.tipo === "listo") {
    return (
      <div role="dialog" aria-label="Cobro registrado" className="cobro-modal">
        <ComprobanteRecibo recibo={fase.cobro} />
        <div className="cobro-acciones">
          <button type="button" className="btn btn-primary btn-sm" onClick={(): void => alCerrar(false)}>
            Listo
          </button>
        </div>
      </div>
    );
  }

  const congelado = fase.tipo === "incierto";
  const enviando = fase.tipo === "enviando";

  return (
    <div role="dialog" aria-label="Cobrar presupuesto" className="cobro-modal">
      <h4>Cobrar presupuesto</h4>
      <form
        aria-label="Datos del cobro"
        noValidate
        onSubmit={(e): void => {
          void enviar(e);
        }}
      >
        {error !== null && (
          <p role="alert" className="banner banner-error">
            {error}
          </p>
        )}
        <div className="field">
          <label htmlFor="cobro-importe">Importe</label>
          <input
            id="cobro-importe"
            className="input"
            type="text"
            inputMode="decimal"
            autoComplete="off"
            value={importe}
            disabled={congelado || enviando}
            onChange={(e): void => setImporte(e.target.value)}
          />
        </div>
        <fieldset disabled={congelado || enviando}>
          <legend>Medio de pago</legend>
          {MEDIOS.map((m) => (
            <label key={m} className="cobro-medio">
              <input
                type="radio"
                name="medio-de-pago"
                value={m}
                checked={medio === m}
                onChange={(): void => setMedio(m)}
              />
              {ETIQUETA_MEDIO[m]}
            </label>
          ))}
        </fieldset>
        <div className="cobro-acciones">
          {congelado ? (
            <>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={(): void => {
                  void enviar();
                }}
              >
                Reintentar
              </button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={(): void => alCerrar(true)}>
                Cerrar
              </button>
            </>
          ) : (
            <>
              <button type="submit" className="btn btn-primary btn-sm" disabled={enviando}>
                Cobrar
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                disabled={enviando}
                onClick={(): void => alCerrar(false)}
              >
                Cancelar
              </button>
            </>
          )}
        </div>
      </form>
    </div>
  );
}

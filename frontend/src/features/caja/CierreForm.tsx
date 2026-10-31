import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "../../shared/api-client";
import { cerrarCaja } from "./api";
import { esContadoValido } from "./tipos";
import type { DatosCierre } from "./tipos";

interface Props {
  cajaId: number;
  /** Se invoca tras un cierre exitoso: el padre vuelve a leer todo desde el servidor. */
  alCerrada: () => Promise<void>;
}

/** Cierre de caja (solo secretaria). El importe se valida como TEXTO y nunca pasa a `number`;
 * la diferencia la calcula el servidor: si exige motivo, se pide sin perder el importe. */
export function CierreForm({ cajaId, alCerrada }: Props): JSX.Element {
  const [contado, setContado] = useState<string>("");
  const [motivo, setMotivo] = useState<string>("");
  const [pideMotivo, setPideMotivo] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<boolean>(false);

  async function enviar(e: FormEvent): Promise<void> {
    e.preventDefault();
    if (enviando) return;
    const importe = contado.trim();
    if (!esContadoValido(importe)) {
      setError("Ingresá un importe válido, por ejemplo 1500.00 (hasta dos decimales).");
      return;
    }
    const motivoLimpio = motivo.trim();
    if (pideMotivo && motivoLimpio === "") {
      setError("El motivo de la diferencia es obligatorio.");
      return;
    }
    const datos: DatosCierre = {
      caja_id: cajaId,
      total_contado: importe,
      ...(pideMotivo ? { motivo_diferencia: motivoLimpio } : {}),
    };
    setError(null);
    setEnviando(true);
    try {
      await cerrarCaja(datos);
      await alCerrada();
    } catch (fallo) {
      if (fallo instanceof ApiError && fallo.httpStatus === 422 && !pideMotivo && /motivo/i.test(fallo.message)) {
        setPideMotivo(true);
      } else {
        setError(fallo instanceof ApiError ? fallo.message : "No se pudo cerrar la caja");
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form
      className="caja-cierre"
      aria-label="Cerrar caja"
      noValidate
      onSubmit={(e): void => {
        void enviar(e);
      }}
    >
      <h3>Cierre del día</h3>
      <p className="muted">
        Contá lo que hay en caja y cargá el total. El sistema calcula la diferencia; si no coincide,
        vas a tener que explicar el motivo.
      </p>
      {error !== null && (
        <p role="alert" className="banner banner-error">
          {error}
        </p>
      )}
      <div className="field">
        <label htmlFor="cierre-contado">Total contado</label>
        <input
          id="cierre-contado"
          className="input"
          type="text"
          inputMode="decimal"
          autoComplete="off"
          placeholder="0.00"
          value={contado}
          onChange={(e): void => setContado(e.target.value)}
        />
      </div>
      {pideMotivo && (
        <div className="field">
          <p role="status" className="banner banner-warning">
            El total contado no coincide con el del sistema: indicá el motivo de la diferencia.
          </p>
          <label htmlFor="cierre-motivo">Motivo de la diferencia</label>
          <input
            id="cierre-motivo"
            className="input"
            type="text"
            maxLength={500}
            value={motivo}
            onChange={(e): void => setMotivo(e.target.value)}
          />
        </div>
      )}
      <button type="submit" className="btn btn-primary" disabled={enviando}>
        Cerrar caja
      </button>
    </form>
  );
}

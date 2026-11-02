import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "../../shared/api-client";
import { generarLiquidacion } from "./api";
import { esPeriodoValido } from "./tipos";
import type { LiquidacionDetalle, ObraSocial } from "./tipos";

interface Props {
  obras: ObraSocial[];
  alGenerada: (detalle: LiquidacionDetalle) => void;
}

/** Genera un borrador por obra social y periodo `AAAA-MM`. El periodo se valida como texto antes
 * de llamar al servidor; el total y las filas las calcula el servidor. */
export function GenerarForm({ obras, alGenerada }: Props): JSX.Element {
  const activas = obras.filter((o) => o.activa);
  const [osId, setOsId] = useState<string>(activas[0] === undefined ? "" : String(activas[0].id));
  const [periodo, setPeriodo] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<boolean>(false);

  async function enviar(e: FormEvent): Promise<void> {
    e.preventDefault();
    if (enviando) return;
    const limpio = periodo.trim();
    if (osId === "") {
      setError("Elegí una obra social.");
      return;
    }
    if (!esPeriodoValido(limpio)) {
      setError("El período debe tener el formato AAAA-MM, por ejemplo 2026-10.");
      return;
    }
    setError(null);
    setEnviando(true);
    try {
      alGenerada(await generarLiquidacion({ os_id: Number(osId), periodo: limpio }));
    } catch (fallo) {
      setError(fallo instanceof ApiError ? fallo.message : "No se pudo generar la liquidación");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form
      className="liq-generar"
      aria-label="Generar liquidación"
      noValidate
      onSubmit={(e): void => {
        void enviar(e);
      }}
    >
      <div className="field">
        <label htmlFor="liq-os">Obra social</label>
        <select id="liq-os" className="input" value={osId} onChange={(e): void => setOsId(e.target.value)}>
          {activas.map((o) => (
            <option key={o.id} value={o.id}>
              {o.nombre}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="liq-periodo">Período (AAAA-MM)</label>
        <input
          id="liq-periodo"
          className="input"
          type="text"
          inputMode="numeric"
          maxLength={7}
          placeholder="2026-10"
          value={periodo}
          aria-invalid={error !== null}
          onChange={(e): void => setPeriodo(e.target.value)}
        />
      </div>
      <button type="submit" className="btn btn-primary btn-sm" disabled={enviando}>
        Generar
      </button>
      {error !== null && (
        <p role="alert" className="banner banner-error">
          {error}
        </p>
      )}
    </form>
  );
}

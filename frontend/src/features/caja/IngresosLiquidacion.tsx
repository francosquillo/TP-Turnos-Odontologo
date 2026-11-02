import { formatearMoneda } from "../../shared/moneda";
import { ETIQUETA_MEDIO } from "./tipos";
import type { IngresoLiquidacion } from "./tipos";

interface Props {
  ingresos: IngresoLiquidacion[];
}

/** "2026-10-01" -> "10/2026" cortando el texto (sin `Date`, que correria el dia en UTC-3). */
function periodoTexto(periodo: string): string {
  const partes = /^(\d{4})-(\d{2})/.exec(periodo);
  return partes === null ? "—" : `${partes[2]}/${partes[1]}`;
}

/** Ingresos de liquidaciones de obras sociales, aparte de los recibos (C-11, D-15): explican
 * el total del cierre. Sin datos de pacientes. El importe viene con su signo del servidor;
 * una reversion se identifica ademas con texto. */
export function IngresosLiquidacion({ ingresos }: Props): JSX.Element {
  return (
    <>
      <h3>Ingresos de obras sociales</h3>
      {ingresos.length === 0 ? (
        <p className="muted">Sin ingresos de obras sociales en este día.</p>
      ) : (
        <ul className="caja-recibos" aria-label="Ingresos de obras sociales">
          {ingresos.map((i, indice) => {
            const esReversion = i.monto.startsWith("-");
            return (
              <li key={`${i.liquidacion_id}-${indice}`} data-reversion={esReversion}>
                <span className="titulo">
                  {esReversion ? "Reversión · " : ""}
                  {i.obra_social} · período {periodoTexto(i.periodo)}
                </span>
                <span className="muted">{ETIQUETA_MEDIO[i.medio]}</span>
                <span className="pres-importe">{formatearMoneda(i.monto)}</span>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}

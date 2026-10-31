import { formatearMoneda } from "../../shared/moneda";
import { etiquetaCara, formatoFecha } from "../odontograma/tipos";
import { ETIQUETA_ESTADO } from "./tipos";
import type { ItemPresupuesto, Presupuesto } from "./tipos";

interface Props {
  presupuesto: Presupuesto;
  /** Contenido adicional (acciones) que el panel agrega debajo del detalle. */
  children?: React.ReactNode;
}

function ubicacion(item: ItemPresupuesto): string | null {
  // El admin recibe la vista financiera: sin pieza ni cara.
  if (item.pieza_fdi === null || item.cara === null) return null;
  return `Pieza ${item.pieza_fdi} · ${etiquetaCara(item.pieza_fdi, item.cara)}`;
}

/** Detalle de solo lectura de un presupuesto; lo reutiliza la cuenta corriente. */
export function PresupuestoDetalle({ presupuesto, children }: Props): JSX.Element {
  const { estado } = presupuesto;
  return (
    <article className="pres-detalle" aria-label={`Presupuesto ${presupuesto.id}`}>
      <header className="pres-detalle-cabecera">
        <h4>Presupuesto {presupuesto.id}</h4>
        <span className="badge" data-pres={estado} aria-label="Estado del presupuesto">
          {ETIQUETA_ESTADO[estado]}
        </span>
        {presupuesto.cargo_anulado && <span className="pres-aviso">Cargo anulado</span>}
      </header>

      <ul className="pres-items" aria-label="Ítems del presupuesto">
        {presupuesto.items.map((item) => {
          const lugar = ubicacion(item);
          return (
            <li key={item.id}>
              <span className="titulo">{item.tratamiento_nombre}</span>
              {lugar !== null && <span className="muted">{lugar}</span>}
              <span className="pres-importe">
                {item.cantidad} × {formatearMoneda(item.precio)} = {formatearMoneda(item.subtotal)}
              </span>
              {!item.hallazgo_vigente && (
                <span className="pres-aviso">
                  El hallazgo ya no está vigente (se corrigió o se dio de baja después de presupuestar).
                </span>
              )}
            </li>
          );
        })}
      </ul>

      <p className="pres-total">
        Total: <strong>{formatearMoneda(presupuesto.total)}</strong>
      </p>
      {presupuesto.presentado_at !== null && (
        <p className="muted">Presentado el {formatoFecha(presupuesto.presentado_at)}</p>
      )}
      {presupuesto.decidido_at !== null && (
        <p className="muted">Decidido el {formatoFecha(presupuesto.decidido_at)}</p>
      )}
      {presupuesto.motivo_rechazo !== null && (
        <p>Motivo del rechazo: {presupuesto.motivo_rechazo}</p>
      )}
      {children}
    </article>
  );
}

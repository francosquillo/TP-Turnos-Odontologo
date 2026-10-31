import { formatearMoneda } from "../../shared/moneda";
import { ETIQUETA_MEDIO, formatearFecha } from "./tipos";
import type { Recibo } from "./tipos";

interface Props {
  recibo: Recibo;
}

/** Comprobante en pantalla (D-19): numero, paciente, importe, medio y fecha. No hay PDF. */
export function ComprobanteRecibo({ recibo }: Props): JSX.Element {
  return (
    <section className="comprobante" aria-label="Comprobante" data-anulado={recibo.anulado}>
      <h4>Recibo N° {recibo.numero}</h4>
      <dl>
        <dt>Paciente</dt>
        <dd>{recibo.paciente_nombre}</dd>
        <dt>Importe</dt>
        <dd>{formatearMoneda(recibo.monto)}</dd>
        <dt>Medio</dt>
        <dd>{ETIQUETA_MEDIO[recibo.medio]}</dd>
        <dt>Fecha</dt>
        <dd>{formatearFecha(recibo.fecha)}</dd>
      </dl>
      {recibo.anulado && (
        <p role="status" className="pres-aviso">
          Este recibo está anulado
          {recibo.motivo_anulacion !== null ? `. Motivo: ${recibo.motivo_anulacion}` : ""}
        </p>
      )}
      <p className="comprobante-leyenda">Pago simulado, sin validez fiscal</p>
    </section>
  );
}

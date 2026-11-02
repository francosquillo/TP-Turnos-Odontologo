import { useState } from "react";
import { ApiError } from "../../shared/api-client";
import { MotivoForm } from "../../shared/MotivoForm";
import { formatearMoneda } from "../../shared/moneda";
import { ETIQUETA_MEDIO, MEDIOS, formatearFecha } from "../caja/tipos";
import type { Medio } from "../caja/tipos";
import {
  cobrarLiquidacion,
  descargarInforme,
  descartarLiquidacion,
  presentarLiquidacion,
  revertirCobroLiquidacion,
} from "./api";
import type { GuardarArchivo } from "./descarga";
import { ETIQUETA_ESTADO, esImportePositivo, periodoATexto } from "./tipos";
import type { FormatoInforme, LiquidacionDetalle } from "./tipos";

interface Props {
  detalle: LiquidacionDetalle;
  /** Solo `admin` opera; el odontologo ve la liquidacion en modo lectura. */
  rol: "admin" | "odontologo";
  guardar: GuardarArchivo;
  alActualizada: (detalle: LiquidacionDetalle) => void;
  alDescartada: () => void;
}

const mensajeDe = (fallo: unknown, porDefecto: string): string =>
  fallo instanceof ApiError ? fallo.message : porDefecto;

/** Detalle por plan con las prestaciones para revision indicadas con texto, y las acciones del
 * admin. Estado, total y subtotales vienen del servidor. Si el servidor rechaza una accion
 * (por ejemplo el cobro con la caja bloqueada), el mensaje se muestra y el medio elegido se
 * conserva. */
export function LiquidacionDetalleVista({ detalle, rol, guardar, alActualizada, alDescartada }: Props): JSX.Element {
  const [medio, setMedio] = useState<Medio>("transferencia");
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<boolean>(false);
  const [revirtiendo, setRevirtiendo] = useState<boolean>(false);

  async function ejecutar(operacion: () => Promise<void>, porDefecto: string): Promise<void> {
    if (ocupado) return;
    setError(null);
    setOcupado(true);
    try {
      await operacion();
    } catch (fallo) {
      setError(mensajeDe(fallo, porDefecto));
    } finally {
      setOcupado(false);
    }
  }

  const presentar = (): Promise<void> =>
    ejecutar(async () => alActualizada(await presentarLiquidacion(detalle.id)), "No se pudo presentar");

  const descartar = (): Promise<void> =>
    ejecutar(async () => {
      await descartarLiquidacion(detalle.id);
      alDescartada();
    }, "No se pudo descartar");

  const cobrar = (): Promise<void> =>
    ejecutar(async () => alActualizada(await cobrarLiquidacion(detalle.id, medio)), "No se pudo cobrar");

  const exportar = (formato: FormatoInforme): Promise<void> =>
    ejecutar(async () => {
      const { blob, nombre } = await descargarInforme(detalle.id, formato);
      guardar(blob, nombre);
    }, "No se pudo exportar");

  async function revertir(motivo: string): Promise<void> {
    setError(null);
    try {
      alActualizada(await revertirCobroLiquidacion(detalle.id, motivo));
      setRevirtiendo(false);
    } catch (fallo) {
      setError(mensajeDe(fallo, "No se pudo revertir el cobro"));
    }
  }

  const esAdmin = rol === "admin";
  const puedeCobrar = detalle.estado === "presentada" && !detalle.revertida;
  const cobrable = esImportePositivo(detalle.total);

  return (
    <section className="liq-detalle" aria-label={`Detalle de la liquidación ${detalle.id}`}>
      <h3>
        {detalle.obra_social} · período {periodoATexto(detalle.periodo)}
      </h3>
      <p className="liq-estado" data-estado={detalle.estado}>
        Estado: <strong>{ETIQUETA_ESTADO[detalle.estado]}</strong>
      </p>
      <p>
        Total a cobrar a la obra social: <strong className="pres-importe">{formatearMoneda(detalle.total)}</strong>
      </p>

      {detalle.cantidad_revision > 0 && (
        <p role="status" aria-label="Aviso de revisión" className="banner banner-warning">
          {detalle.cantidad_revision} prestación{detalle.cantidad_revision === 1 ? "" : "es"} para revisión
          manual: no se liquida{detalle.cantidad_revision === 1 ? "" : "n"} ni suma{detalle.cantidad_revision === 1 ? "" : "n"} al
          total. Reclamarla a la obra social y devolver al paciente se resuelve fuera del sistema.
        </p>
      )}

      {detalle.planes.map((plan) => (
        <div key={plan.plan_id} className="liq-plan">
          <h4>Plan: {plan.plan_nombre}</h4>
          {plan.items.length === 0 ? (
            <p className="muted">Sin prestaciones.</p>
          ) : (
            <ul className="liq-items" aria-label={`Prestaciones del plan ${plan.plan_nombre}`}>
              {plan.items.map((i) => (
                <li key={i.id} data-revision={i.revision}>
                  <span className="titulo">
                    {formatearFecha(i.fecha_prestacion)} · {i.paciente_nombre}
                  </span>
                  <span className="muted">
                    {i.codigo} · {i.descripcion} × {i.cantidad}
                  </span>
                  <span className="pres-importe">{formatearMoneda(i.monto)}</span>
                  {i.revision && <span className="pres-aviso">Para revisión manual · No se liquida</span>}
                </li>
              ))}
            </ul>
          )}
          <p>
            Subtotal {plan.plan_nombre}: <strong className="pres-importe">{formatearMoneda(plan.subtotal)}</strong>
          </p>
        </div>
      ))}

      {error !== null && (
        <p role="alert" className="banner banner-error">
          {error}
        </p>
      )}

      {!esAdmin && <p className="muted">Vista de solo lectura.</p>}

      {esAdmin && (
        <div className="liq-acciones">
          {detalle.estado === "borrador" && (
            <>
              <button type="button" className="btn btn-primary btn-sm" disabled={ocupado} onClick={(): void => void presentar()}>
                Presentar
              </button>
              <button type="button" className="btn btn-danger btn-sm" disabled={ocupado} onClick={(): void => void descartar()}>
                Descartar
              </button>
            </>
          )}
          <button type="button" className="btn btn-secondary btn-sm" disabled={ocupado} onClick={(): void => void exportar("csv")}>
            Exportar CSV
          </button>
          <button type="button" className="btn btn-secondary btn-sm" disabled={ocupado} onClick={(): void => void exportar("pdf")}>
            Exportar PDF
          </button>
        </div>
      )}

      {esAdmin && puedeCobrar && cobrable && (
        <div className="liq-cobro">
          <div className="field">
            <label htmlFor={`liq-medio-${detalle.id}`}>Medio de cobro</label>
            <select
              id={`liq-medio-${detalle.id}`}
              className="input"
              value={medio}
              onChange={(e): void => setMedio(e.target.value as Medio)}
            >
              {MEDIOS.map((m) => (
                <option key={m} value={m}>
                  {ETIQUETA_MEDIO[m]}
                </option>
              ))}
            </select>
          </div>
          <button type="button" className="btn btn-primary btn-sm" disabled={ocupado} onClick={(): void => void cobrar()}>
            Cobrar liquidación
          </button>
        </div>
      )}

      {esAdmin && puedeCobrar && !cobrable && (
        <p className="muted">La liquidación no tiene importe para cobrar: todas sus prestaciones están en revisión.</p>
      )}

      {detalle.revertida && detalle.estado === "presentada" && (
        <p role="status" className="banner banner-info">
          Cobro revertido: no se puede volver a cobrar.
        </p>
      )}

      {esAdmin && detalle.estado === "cobrada" && !revirtiendo && (
        <button type="button" className="btn btn-danger btn-sm" onClick={(): void => setRevirtiendo(true)}>
          Revertir cobro
        </button>
      )}

      {esAdmin && detalle.estado === "cobrada" && revirtiendo && (
        <MotivoForm
          idBase={`liq-revertir-${detalle.id}`}
          etiqueta="Motivo de la reversión"
          textoBoton="Confirmar reversión"
          peligro
          alConfirmar={revertir}
          alCancelar={(): void => setRevirtiendo(false)}
        />
      )}
    </section>
  );
}

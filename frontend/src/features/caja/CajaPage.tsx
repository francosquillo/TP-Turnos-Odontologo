import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "../../shared/api-client";
import { formatearMoneda } from "../../shared/moneda";
import { anularRecibo, consultarCaja, listarRecibos } from "./api";
import { CierreForm } from "./CierreForm";
import { IngresosLiquidacion } from "./IngresosLiquidacion";
import { RecibosLista } from "./RecibosLista";
import { ETIQUETA_MEDIO, formatearFecha } from "./tipos";
import type { EstadoCaja, Recibo } from "./tipos";

interface Props {
  /** Solo `secretaria` cierra; el admin consulta y anula recibos. */
  rol: "secretaria" | "admin";
}

type Carga =
  | { tipo: "cargando" }
  | { tipo: "error"; mensaje: string }
  | { tipo: "lista"; estado: EstadoCaja; recibos: Recibo[] };

const mensajeDe = (fallo: unknown): string =>
  fallo instanceof ApiError ? fallo.message : "No se pudo cargar la caja";

function AvisoBloqueo({ estado }: { estado: EstadoCaja }): JSX.Element | null {
  if (estado.bloqueo === "caja_pendiente") {
    const pendiente = estado.caja !== null && estado.caja.estado === "abierta" ? estado.caja.fecha : null;
    return (
      <p role="alert" className="banner banner-warning">
        {pendiente !== null
          ? `Hay una caja sin cerrar del ${formatearFecha(pendiente)}. `
          : "Hay una caja anterior sin cerrar. "}
        Hay que cerrarla para poder cobrar y anular recibos.
      </p>
    );
  }
  if (estado.bloqueo === "caja_cerrada") {
    return (
      <p role="status" className="banner banner-info">
        La caja de hoy ya está cerrada: los cobros se retoman mañana.
      </p>
    );
  }
  return null;
}

export function CajaPage({ rol }: Props): JSX.Element {
  const [carga, setCarga] = useState<Carga>({ tipo: "cargando" });
  const [fechaPedida, setFechaPedida] = useState<string | undefined>(undefined);
  const [campoFecha, setCampoFecha] = useState<string>("");

  const cargar = useCallback(async (fecha: string | undefined): Promise<void> => {
    try {
      const estado = await consultarCaja(fecha);
      const recibos = await listarRecibos(estado.fecha);
      setCarga({ tipo: "lista", estado, recibos });
    } catch (fallo) {
      setCarga({ tipo: "error", mensaje: mensajeDe(fallo) });
    }
  }, []);

  useEffect(() => {
    setCarga({ tipo: "cargando" });
    void cargar(fechaPedida);
  }, [cargar, fechaPedida]);

  function consultarOtroDia(e: FormEvent): void {
    e.preventDefault();
    setFechaPedida(/^\d{4}-\d{2}-\d{2}$/.test(campoFecha) ? campoFecha : undefined);
  }

  if (carga.tipo === "cargando") {
    return (
      <section className="caja" aria-label="Caja">
        <p className="muted">Cargando caja…</p>
      </section>
    );
  }

  if (carga.tipo === "error") {
    return (
      <section className="caja" aria-label="Caja">
        <p role="alert" className="banner banner-error">
          {carga.mensaje}
        </p>
      </section>
    );
  }

  const { estado, recibos } = carga;
  const caja = estado.caja;

  async function anular(reciboId: number, motivo: string): Promise<void> {
    await anularRecibo(reciboId, motivo);
    await cargar(fechaPedida);
  }

  return (
    <section className="caja" aria-label="Caja">
      <div className="caja-cabecera">
        <h2>Caja del {formatearFecha(estado.fecha)}</h2>
        <form className="caja-otro-dia" onSubmit={consultarOtroDia}>
          <label htmlFor="caja-otro-dia">Ver otro día</label>
          <input
            id="caja-otro-dia"
            className="input"
            type="date"
            value={campoFecha}
            onChange={(e): void => setCampoFecha(e.target.value)}
          />
          <button type="submit" className="btn btn-secondary btn-sm">
            Consultar
          </button>
        </form>
      </div>

      <AvisoBloqueo estado={estado} />

      {caja === null ? (
        <p className="muted">Todavía no hay movimientos: la caja se abre sola con el primer cobro.</p>
      ) : (
        <div className="caja-resumen" data-estado={caja.estado}>
          <p className="caja-estado">{caja.estado === "abierta" ? "Caja abierta" : "Caja cerrada"}</p>
          <p>
            Total del sistema: <strong>{formatearMoneda(caja.total_sistema)}</strong>
          </p>
          {caja.estado === "cerrada" && caja.total_contado !== null && caja.diferencia !== null && (
            <>
              <p>
                Total contado: <strong>{formatearMoneda(caja.total_contado)}</strong>
              </p>
              <p>
                Diferencia: <strong>{formatearMoneda(caja.diferencia)}</strong>
              </p>
              {caja.motivo_diferencia !== null && (
                <p className="muted">Motivo de la diferencia: {caja.motivo_diferencia}</p>
              )}
            </>
          )}
        </div>
      )}

      {estado.desglose.length > 0 && (
        <ul className="caja-desglose" aria-label="Desglose por medio">
          {estado.desglose.map((d) => (
            <li key={d.medio}>
              <span>{ETIQUETA_MEDIO[d.medio]}</span>
              <span className="pres-importe">{formatearMoneda(d.subtotal)}</span>
            </li>
          ))}
        </ul>
      )}

      <IngresosLiquidacion ingresos={estado.ingresos_liquidacion} />

      {rol === "secretaria" && caja !== null && caja.estado === "abierta" && (
        <CierreForm cajaId={caja.id} alCerrada={(): Promise<void> => cargar(fechaPedida)} />
      )}

      <h3>Recibos del día</h3>
      <RecibosLista recibos={recibos} rol={rol} alAnular={anular} />
    </section>
  );
}

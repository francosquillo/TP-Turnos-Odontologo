import { useEffect, useState } from "react";
import { ApiError } from "../../shared/api-client";
import { estadoDeSaldo, formatearMoneda } from "../../shared/moneda";
import { formatoFecha } from "../odontograma/tipos";
import { obtenerPresupuesto } from "../presupuestos/api";
import { PresupuestoDetalle } from "../presupuestos/PresupuestoDetalle";
import type { Presupuesto } from "../presupuestos/tipos";
import { anularMovimiento, consultarCuenta } from "./api";
import { AnularModal } from "./AnularModal";
import { ETIQUETA_TIPO } from "./tipos";
import type { Cuenta, Movimiento } from "./tipos";

interface Props {
  pacienteId: number;
  pacienteNombre: string;
  /** Solo `admin` anula; la secretaria solo consulta. */
  rol: "secretaria" | "admin";
  alVolver: () => void;
}

type Carga = { tipo: "cargando" } | { tipo: "error"; mensaje: string } | { tipo: "lista"; cuenta: Cuenta };

function mensajeDe(error: unknown): string {
  return error instanceof ApiError ? error.message : "No se pudo cargar la cuenta corriente";
}

/** El saldo a favor se muestra sin signo: el texto ya dice de quien es. */
const sinSigno = (importe: string): string => importe.replace(/^-/, "");

function ResumenSaldo({ saldo }: { saldo: string }): JSX.Element {
  const estado = estadoDeSaldo(saldo);
  return (
    <p role="status" className="cuenta-saldo" data-saldo={estado}>
      {estado === "debe" && (
        <>
          El paciente debe <strong>{formatearMoneda(saldo)}</strong>
        </>
      )}
      {estado === "sin-deuda" && <>El paciente está sin deuda</>}
      {estado === "a-favor" && (
        <>
          El paciente tiene saldo a favor: <strong>{formatearMoneda(sinSigno(saldo))}</strong>
        </>
      )}
    </p>
  );
}

export function CuentaPage({ pacienteId, pacienteNombre, rol, alVolver }: Props): JSX.Element {
  const [carga, setCarga] = useState<Carga>({ tipo: "cargando" });
  const [aAnular, setAAnular] = useState<Movimiento | null>(null);
  const [presupuesto, setPresupuesto] = useState<Presupuesto | null>(null);
  const [avisoPresupuesto, setAvisoPresupuesto] = useState<string | null>(null);

  useEffect(() => {
    let vigente = true;
    setCarga({ tipo: "cargando" });
    setAAnular(null);
    setPresupuesto(null);
    consultarCuenta(pacienteId)
      .then((cuenta) => {
        if (vigente) setCarga({ tipo: "lista", cuenta });
      })
      .catch((fallo: unknown) => {
        if (vigente) setCarga({ tipo: "error", mensaje: mensajeDe(fallo) });
      });
    return (): void => {
      vigente = false;
    };
  }, [pacienteId]);

  const encabezado = (
    <div className="cuenta-cabecera">
      <h2>Cuenta corriente · {pacienteNombre}</h2>
      <button type="button" className="btn btn-secondary btn-sm" onClick={alVolver}>
        Volver a la agenda
      </button>
    </div>
  );

  if (carga.tipo === "cargando") {
    return (
      <section className="cuenta" aria-label="Cuenta corriente">
        {encabezado}
        <p className="muted">Cargando cuenta corriente…</p>
      </section>
    );
  }

  if (carga.tipo === "error") {
    return (
      <section className="cuenta" aria-label="Cuenta corriente">
        {encabezado}
        <p role="alert" className="banner banner-error">
          {carga.mensaje}
        </p>
      </section>
    );
  }

  const { cuenta } = carga;

  async function anular(movimiento: Movimiento, motivo: string): Promise<void> {
    await anularMovimiento(pacienteId, movimiento.id, motivo);
    // El saldo y las marcas de anulado los deriva el servidor: se vuelve a consultar.
    setCarga({ tipo: "lista", cuenta: await consultarCuenta(pacienteId) });
    setAAnular(null);
  }

  async function abrirPresupuesto(id: number): Promise<void> {
    setAvisoPresupuesto(null);
    try {
      setPresupuesto(await obtenerPresupuesto(id));
    } catch (fallo) {
      setAvisoPresupuesto(mensajeDe(fallo));
    }
  }

  return (
    <section className="cuenta" aria-label="Cuenta corriente">
      {encabezado}
      <ResumenSaldo saldo={cuenta.saldo} />

      {cuenta.movimientos.length === 0 ? (
        <p className="muted">El paciente no tiene movimientos.</p>
      ) : (
        <ul className="cuenta-movimientos" aria-label="Movimientos">
          {cuenta.movimientos.map((m) => (
            <li key={m.id} data-anulado={m.anulado}>
              <span className="titulo">
                {ETIQUETA_TIPO[m.tipo]} · {m.concepto}
              </span>
              <span className="pres-importe">{formatearMoneda(m.monto)}</span>
              <span className="muted">{formatoFecha(m.created_at)}</span>
              {m.anulado && <span className="pres-aviso">Anulado</span>}
              {m.anula_a_id !== null && <span className="muted">Anula el movimiento {m.anula_a_id}</span>}
              {m.motivo !== null && <span className="muted">Motivo: {m.motivo}</span>}
              <span className="cuenta-acciones">
                {m.presupuesto_id !== null && (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    aria-label={`Ver presupuesto ${m.presupuesto_id}`}
                    onClick={(): void => {
                      if (m.presupuesto_id !== null) void abrirPresupuesto(m.presupuesto_id);
                    }}
                  >
                    Ver presupuesto
                  </button>
                )}
                {rol === "admin" && m.tipo === "cargo" && !m.anulado && (
                  <button
                    type="button"
                    className="btn btn-danger btn-sm"
                    aria-label={`Anular cargo ${m.id}`}
                    onClick={(): void => setAAnular(m)}
                  >
                    Anular
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}

      {avisoPresupuesto !== null && (
        <p role="alert" className="banner banner-error">
          {avisoPresupuesto}
        </p>
      )}
      {presupuesto !== null && (
        <PresupuestoDetalle presupuesto={presupuesto}>
          <div className="cuenta-acciones">
            <button type="button" className="btn btn-ghost btn-sm" onClick={(): void => setPresupuesto(null)}>
              Cerrar presupuesto
            </button>
          </div>
        </PresupuestoDetalle>
      )}

      {aAnular !== null && (
        <AnularModal
          movimiento={aAnular}
          alCerrar={(): void => setAAnular(null)}
          alConfirmar={(motivo): Promise<void> => anular(aAnular, motivo)}
        />
      )}
    </section>
  );
}

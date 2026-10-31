import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "../../shared/api-client";
import { formatearMoneda } from "../../shared/moneda";
import { etiquetaCara } from "../odontograma/tipos";
import type { Hallazgo } from "../odontograma/tipos";
import type { ItemEntrada, Presupuesto, Tratamiento } from "./tipos";

interface Props {
  /** Prefijo unico para los ids de los campos. */
  idBase: string;
  /** Hallazgos de la historia (se ofrecen solo los activos). */
  hallazgos: readonly Hallazgo[];
  nombres: Readonly<Record<string, string>>;
  tratamientos: readonly Tratamiento[];
  /** Items de partida al editar un borrador. */
  inicial?: readonly ItemEntrada[];
  etiquetaBoton: string;
  alEnviar: (items: ItemEntrada[]) => Promise<Presupuesto>;
  alCancelar?: () => void;
}

interface Fila {
  clave: number;
  hallazgoId: string;
  tratamientoId: string;
  cantidad: string;
}

function mensajeDe(error: unknown): string {
  return error instanceof ApiError ? error.message : "No se pudo guardar el presupuesto";
}

export function etiquetaHallazgo(h: Hallazgo, nombres: Readonly<Record<string, string>>): string {
  return `Pieza ${h.pieza_fdi} · ${etiquetaCara(h.pieza_fdi, h.cara)} · ${nombres[h.estado] ?? h.estado}`;
}

const cantidadValida = (texto: string): boolean => /^\d+$/.test(texto) && Number(texto) >= 1 && Number(texto) <= 99;

export function PresupuestoForm({
  idBase,
  hallazgos,
  nombres,
  tratamientos,
  inicial,
  etiquetaBoton,
  alEnviar,
  alCancelar,
}: Props): JSX.Element {
  const [filas, setFilas] = useState<Fila[]>(() =>
    (inicial ?? []).map((item, i) => ({
      clave: i,
      hallazgoId: String(item.hallazgo_id),
      tratamientoId: String(item.tratamiento_id),
      cantidad: String(item.cantidad),
    })),
  );
  const [siguiente, setSiguiente] = useState<number>(inicial?.length ?? 0);
  const [error, setError] = useState<string | null>(null);
  const [totalServidor, setTotalServidor] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<boolean>(false);

  // Estado derivado en render: nada de efectos para validar.
  const activos = hallazgos.filter((h) => h.deleted_at === null);
  const idsActivos = new Set(activos.map((h) => String(h.id)));
  const pares = filas.map((f) => `${f.hallazgoId}:${f.tratamientoId}`);
  const hayRepetidos = new Set(pares).size !== pares.length;
  const hayNoVigentes = filas.some((f) => !idsActivos.has(f.hallazgoId));
  const hayCantidadInvalida = filas.some((f) => !cantidadValida(f.cantidad));
  const incompleto = filas.length === 0 || hayRepetidos || hayNoVigentes || hayCantidadInvalida;

  function agregar(): void {
    const primerHallazgo = activos[0];
    const primerTratamiento = tratamientos[0];
    if (primerHallazgo === undefined || primerTratamiento === undefined) return;
    setFilas((previas) => [
      ...previas,
      {
        clave: siguiente,
        hallazgoId: String(primerHallazgo.id),
        tratamientoId: String(primerTratamiento.id),
        cantidad: "1",
      },
    ]);
    setSiguiente((n) => n + 1);
  }

  function cambiar(clave: number, cambios: Partial<Fila>): void {
    setFilas((previas) => previas.map((f) => (f.clave === clave ? { ...f, ...cambios } : f)));
  }

  function quitar(clave: number): void {
    setFilas((previas) => previas.filter((f) => f.clave !== clave));
  }

  async function enviar(e: FormEvent): Promise<void> {
    e.preventDefault();
    if (incompleto || enviando) return;
    setEnviando(true);
    setError(null);
    try {
      const guardado = await alEnviar(
        filas.map((f) => ({
          hallazgo_id: Number(f.hallazgoId),
          tratamiento_id: Number(f.tratamientoId),
          cantidad: Number(f.cantidad),
        })),
      );
      setTotalServidor(guardado.total);
    } catch (fallo) {
      setError(mensajeDe(fallo));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form
      className="pres-form"
      aria-label={etiquetaBoton}
      onSubmit={(e): void => {
        void enviar(e);
      }}
    >
      {filas.length === 0 && <p className="muted">Agregá al menos un ítem para armar el presupuesto.</p>}
      {filas.map((fila, indice) => {
        const base = `${idBase}-${fila.clave}`;
        const vigente = idsActivos.has(fila.hallazgoId);
        return (
          <fieldset key={fila.clave} className="pres-item-form">
            <legend>Ítem {indice + 1}</legend>
            <div className="row">
              <div className="field">
                <label htmlFor={`${base}-hallazgo`}>Hallazgo (ítem {indice + 1})</label>
                <select
                  id={`${base}-hallazgo`}
                  className="input"
                  value={fila.hallazgoId}
                  onChange={(e): void => cambiar(fila.clave, { hallazgoId: e.target.value })}
                >
                  {!vigente && <option value={fila.hallazgoId}>Hallazgo no disponible</option>}
                  {activos.map((h) => (
                    <option key={h.id} value={h.id}>
                      {etiquetaHallazgo(h, nombres)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor={`${base}-tratamiento`}>Tratamiento (ítem {indice + 1})</label>
                <select
                  id={`${base}-tratamiento`}
                  className="input"
                  value={fila.tratamientoId}
                  onChange={(e): void => cambiar(fila.clave, { tratamientoId: e.target.value })}
                >
                  {tratamientos.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.nombre}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor={`${base}-cantidad`}>Cantidad (ítem {indice + 1})</label>
                <input
                  id={`${base}-cantidad`}
                  className="input"
                  type="number"
                  min={1}
                  max={99}
                  value={fila.cantidad}
                  aria-invalid={!cantidadValida(fila.cantidad)}
                  onChange={(e): void => cambiar(fila.clave, { cantidad: e.target.value })}
                />
              </div>
            </div>
            {!vigente && (
              <p className="pres-aviso">Este hallazgo ya no está vigente: quitá el ítem o elegí el hallazgo nuevo.</p>
            )}
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              aria-label={`Quitar ítem ${indice + 1}`}
              onClick={(): void => quitar(fila.clave)}
            >
              Quitar
            </button>
          </fieldset>
        );
      })}
      {hayRepetidos && <p className="pres-aviso">Hay ítems repetidos (mismo hallazgo y tratamiento).</p>}
      {error !== null && (
        <p role="alert" className="banner banner-error">
          {error}
        </p>
      )}
      <p className="muted">
        {totalServidor === null ? "El total lo calcula el servidor al guardar." : null}
      </p>
      {totalServidor !== null && (
        <p role="status" className="pres-total">
          Total calculado por el servidor: <strong>{formatearMoneda(totalServidor)}</strong>
        </p>
      )}
      <div className="pres-acciones">
        <button type="button" className="btn btn-secondary btn-sm" onClick={agregar}>
          Agregar ítem
        </button>
        <button type="submit" className="btn btn-primary" disabled={incompleto || enviando}>
          {etiquetaBoton}
        </button>
        {alCancelar !== undefined && (
          <button type="button" className="btn btn-ghost" onClick={alCancelar}>
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}

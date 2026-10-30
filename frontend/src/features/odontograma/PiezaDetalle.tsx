import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "../../shared/api-client";
import { HallazgoForm } from "./HallazgoForm";
import { CARAS, estadoVigente, etiquetaCara, formatoFecha, ordenarHistorial } from "./tipos";
import type { Catalogo, DatosHallazgo, Hallazgo } from "./tipos";

interface Props {
  pieza: number;
  /** Hallazgos de toda la historia (se filtra la pieza aca), anulados incluidos. */
  hallazgos: readonly Hallazgo[];
  catalogo: Catalogo;
  nombres: Readonly<Record<string, string>>;
  rol: "odontologo" | "secretaria";
  alRegistrar: (datos: DatosHallazgo) => Promise<void>;
  alCorregir: (id: number, datos: DatosHallazgo, motivo: string) => Promise<void>;
  alBaja: (id: number, motivo: string) => Promise<void>;
  alCerrar: () => void;
}

type Accion = { tipo: "corregir" | "baja"; id: number } | null;

function mensajeDe(error: unknown): string {
  return error instanceof ApiError ? error.message : "No se pudo completar la operación";
}

interface BajaFormProps {
  id: number;
  alConfirmar: (motivo: string) => Promise<void>;
  alCancelar: () => void;
}

function BajaForm({ id, alConfirmar, alCancelar }: BajaFormProps): JSX.Element {
  const [motivo, setMotivo] = useState<string>("");
  const limpio = motivo.trim();

  function enviar(e: FormEvent): void {
    e.preventDefault();
    if (limpio !== "") void alConfirmar(limpio);
  }

  return (
    <form className="odonto-baja-form" aria-label="Dar de baja el hallazgo" onSubmit={enviar}>
      <div className="field">
        <label htmlFor={`baja-${id}-motivo`}>Motivo de la baja</label>
        <input
          id={`baja-${id}-motivo`}
          className="input"
          type="text"
          maxLength={500}
          value={motivo}
          onChange={(e): void => setMotivo(e.target.value)}
        />
      </div>
      <div className="odonto-acciones">
        <button type="submit" className="btn btn-danger btn-sm" disabled={limpio === ""}>
          Confirmar baja
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={alCancelar}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

export function PiezaDetalle({
  pieza,
  hallazgos,
  catalogo,
  nombres,
  rol,
  alRegistrar,
  alCorregir,
  alBaja,
  alCerrar,
}: Props): JSX.Element {
  const [accion, setAccion] = useState<Accion>(null);
  const [error, setError] = useState<string | null>(null);

  const propios = hallazgos.filter((h) => h.pieza_fdi === pieza);
  const historial = ordenarHistorial(propios);
  const vigente = estadoVigente(propios);
  const nombreDe = (estado: string): string => nombres[estado] ?? estado;
  const puedeEscribir = rol === "odontologo";

  async function ejecutar(operacion: () => Promise<void>, cierra: boolean): Promise<void> {
    setError(null);
    try {
      await operacion();
      if (cierra) setAccion(null);
    } catch (fallo) {
      setError(mensajeDe(fallo));
    }
  }

  return (
    <section className="odonto-detalle" aria-label={`Detalle de la pieza ${pieza}`}>
      <div className="odonto-cabecera">
        <h3>Pieza {pieza}</h3>
        <button type="button" className="btn btn-ghost btn-sm" onClick={alCerrar}>
          Cerrar detalle
        </button>
      </div>

      {error !== null && (
        <p role="alert" className="banner banner-error">
          {error}
        </p>
      )}

      {vigente.size > 0 && (
        <ul className="odonto-vigente" aria-label="Estado vigente">
          {CARAS.filter((c) => vigente.has(c)).map((cara) => (
            <li key={cara}>
              <span className="badge" data-espera="activa">
                {nombreDe(vigente.get(cara)?.estado ?? "")} · {etiquetaCara(pieza, cara)}
              </span>
            </li>
          ))}
        </ul>
      )}

      {historial.length === 0 ? (
        <p className="muted">Sin registros para esta pieza.</p>
      ) : (
        <ol className="odonto-historial" aria-label={`Historial de la pieza ${pieza}`}>
          {historial.map((h) => {
            const anulado = h.deleted_at !== null;
            return (
              <li key={h.id} data-anulado={anulado}>
                <span className="titulo">
                  {nombreDe(h.estado)} · {etiquetaCara(pieza, h.cara)}
                </span>
                <span className="muted">Registrado el {formatoFecha(h.fecha)}</span>
                {anulado && h.deleted_at !== null && (
                  <span>
                    Dado de baja el {formatoFecha(h.deleted_at)}: {h.motivo_baja}
                  </span>
                )}
                {puedeEscribir && h.es_propio && !anulado && (
                  <div className="odonto-acciones">
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={(): void => setAccion({ tipo: "corregir", id: h.id })}
                    >
                      Corregir
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={(): void => setAccion({ tipo: "baja", id: h.id })}
                    >
                      Dar de baja
                    </button>
                  </div>
                )}
                {accion?.id === h.id && accion.tipo === "corregir" && (
                  <HallazgoForm
                    idBase={`corregir-${h.id}`}
                    pieza={pieza}
                    catalogo={catalogo}
                    inicial={{ estado: h.estado, cara: h.cara }}
                    pedirMotivo
                    etiquetaBoton="Guardar corrección"
                    alEnviar={(datos, motivo): Promise<void> =>
                      ejecutar(() => alCorregir(h.id, datos, motivo), true)
                    }
                    alCancelar={(): void => setAccion(null)}
                  />
                )}
                {accion?.id === h.id && accion.tipo === "baja" && (
                  <BajaForm
                    id={h.id}
                    alConfirmar={(motivo): Promise<void> => ejecutar(() => alBaja(h.id, motivo), true)}
                    alCancelar={(): void => setAccion(null)}
                  />
                )}
              </li>
            );
          })}
        </ol>
      )}

      {puedeEscribir && (
        <HallazgoForm
          idBase="nuevo"
          pieza={pieza}
          catalogo={catalogo}
          pedirMotivo={false}
          etiquetaBoton="Registrar hallazgo"
          alEnviar={(datos): Promise<void> => ejecutar(() => alRegistrar(datos), false)}
        />
      )}
    </section>
  );
}

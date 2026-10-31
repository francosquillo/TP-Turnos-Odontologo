import { useEffect, useState } from "react";
import { ApiError } from "../../shared/api-client";
import { MotivoForm } from "../../shared/MotivoForm";
import { formatearMoneda } from "../../shared/moneda";
import type { Hallazgo } from "../odontograma/tipos";
import {
  aceptarPresupuesto,
  crearPresupuesto,
  darDeBajaPresupuesto,
  listarPresupuestos,
  listarTratamientos,
  presentarPresupuesto,
  rechazarPresupuesto,
  reemplazarItems,
} from "./api";
import { PresupuestoDetalle } from "./PresupuestoDetalle";
import { PresupuestoForm } from "./PresupuestoForm";
import { ETIQUETA_ESTADO } from "./tipos";
import type { ItemEntrada, Presupuesto, Tratamiento } from "./tipos";

interface Props {
  pacienteId: number;
  /** Hallazgos de la historia ya cargados por el odontograma: no hay otro fetch. */
  hallazgos: readonly Hallazgo[];
  nombres: Readonly<Record<string, string>>;
  rol: "odontologo" | "secretaria";
}

type Carga =
  | { tipo: "cargando" }
  | { tipo: "error"; mensaje: string }
  | { tipo: "listo"; lista: Presupuesto[]; tratamientos: Tratamiento[] };

type Modo =
  | { tipo: "ver" }
  | { tipo: "nuevo" }
  | { tipo: "editar" }
  | { tipo: "rechazar" }
  | { tipo: "baja" };

function mensajeDe(error: unknown): string {
  return error instanceof ApiError ? error.message : "No se pudo completar la operación";
}

const aEntradas = (p: Presupuesto): ItemEntrada[] =>
  p.items.map((i) => ({ hallazgo_id: i.hallazgo_id, tratamiento_id: i.tratamiento_id, cantidad: i.cantidad }));

export function PresupuestosPanel({ pacienteId, hallazgos, nombres, rol }: Props): JSX.Element {
  const [carga, setCarga] = useState<Carga>({ tipo: "cargando" });
  const [seleccionadoId, setSeleccionadoId] = useState<number | null>(null);
  const [modo, setModo] = useState<Modo>({ tipo: "ver" });
  const [aviso, setAviso] = useState<string | null>(null);

  const esOdontologo = rol === "odontologo";

  useEffect(() => {
    let vigente = true;
    setCarga({ tipo: "cargando" });
    setSeleccionadoId(null);
    setModo({ tipo: "ver" });
    setAviso(null);
    // Fetches independientes en paralelo; la secretaria no necesita el catalogo.
    Promise.all([
      listarPresupuestos(pacienteId),
      esOdontologo ? listarTratamientos() : Promise.resolve<Tratamiento[]>([]),
    ])
      .then(([lista, tratamientos]) => {
        if (vigente) setCarga({ tipo: "listo", lista, tratamientos });
      })
      .catch((fallo: unknown) => {
        if (vigente) setCarga({ tipo: "error", mensaje: mensajeDe(fallo) });
      });
    return (): void => {
      vigente = false;
    };
  }, [pacienteId, esOdontologo]);

  if (carga.tipo === "cargando") {
    return (
      <section className="pres-panel" aria-label="Presupuestos">
        <h3>Presupuestos</h3>
        <p className="muted">Cargando presupuestos…</p>
      </section>
    );
  }

  if (carga.tipo === "error") {
    return (
      <section className="pres-panel" aria-label="Presupuestos">
        <h3>Presupuestos</h3>
        <p role="alert" className="banner banner-error">
          {carga.mensaje}
        </p>
      </section>
    );
  }

  const { lista, tratamientos } = carga;
  const seleccionado = lista.find((p) => p.id === seleccionadoId) ?? null;
  const hayHallazgosActivos = hallazgos.some((h) => h.deleted_at === null);

  function aplicar(guardado: Presupuesto): void {
    setCarga((previo) => {
      if (previo.tipo !== "listo") return previo;
      const existe = previo.lista.some((p) => p.id === guardado.id);
      const siguiente = existe
        ? previo.lista.map((p) => (p.id === guardado.id ? guardado : p))
        : [guardado, ...previo.lista];
      return { ...previo, lista: siguiente };
    });
    setSeleccionadoId(guardado.id);
  }

  function quitar(id: number): void {
    setCarga((previo) =>
      previo.tipo === "listo" ? { ...previo, lista: previo.lista.filter((p) => p.id !== id) } : previo,
    );
    setSeleccionadoId(null);
  }

  /** Ejecuta una operacion: ante un error (409 incluido) la pantalla y las acciones se conservan. */
  async function ejecutar(operacion: () => Promise<void>): Promise<void> {
    setAviso(null);
    try {
      await operacion();
    } catch (fallo) {
      setAviso(mensajeDe(fallo));
    }
  }

  function acciones(p: Presupuesto): JSX.Element | null {
    if (!esOdontologo || !p.es_propio) return null;
    if (modo.tipo === "rechazar") {
      return (
        <MotivoForm
          idBase={`rechazo-${p.id}`}
          etiqueta="Motivo del rechazo"
          textoBoton="Confirmar rechazo"
          peligro
          alCancelar={(): void => setModo({ tipo: "ver" })}
          alConfirmar={(motivo): Promise<void> =>
            ejecutar(async () => {
              aplicar(await rechazarPresupuesto(p.id, motivo));
              setModo({ tipo: "ver" });
            })
          }
        />
      );
    }
    if (modo.tipo === "baja") {
      return (
        <MotivoForm
          idBase={`baja-${p.id}`}
          etiqueta="Motivo de la baja"
          textoBoton="Confirmar baja"
          peligro
          alCancelar={(): void => setModo({ tipo: "ver" })}
          alConfirmar={(motivo): Promise<void> =>
            ejecutar(async () => {
              await darDeBajaPresupuesto(p.id, motivo);
              quitar(p.id);
              setModo({ tipo: "ver" });
            })
          }
        />
      );
    }
    if (modo.tipo === "editar" && p.estado === "borrador") {
      return (
        <PresupuestoForm
          idBase={`editar-${p.id}`}
          hallazgos={hallazgos}
          nombres={nombres}
          tratamientos={tratamientos}
          inicial={aEntradas(p)}
          etiquetaBoton="Guardar cambios"
          alCancelar={(): void => setModo({ tipo: "ver" })}
          alEnviar={async (items): Promise<Presupuesto> => {
            const guardado = await reemplazarItems(p.id, items);
            aplicar(guardado);
            return guardado;
          }}
        />
      );
    }
    if (p.estado === "borrador") {
      return (
        <div className="pres-acciones">
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={(): void => {
              void ejecutar(async () => aplicar(await presentarPresupuesto(p.id)));
            }}
          >
            Presentar
          </button>
          <button type="button" className="btn btn-secondary btn-sm" onClick={(): void => setModo({ tipo: "editar" })}>
            Editar ítems
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={(): void => setModo({ tipo: "baja" })}>
            Dar de baja
          </button>
        </div>
      );
    }
    if (p.estado === "presentado") {
      return (
        <div className="pres-acciones">
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={(): void => {
              void ejecutar(async () => aplicar(await aceptarPresupuesto(p.id)));
            }}
          >
            Aceptar
          </button>
          <button type="button" className="btn btn-danger btn-sm" onClick={(): void => setModo({ tipo: "rechazar" })}>
            Rechazar
          </button>
        </div>
      );
    }
    return null;
  }

  return (
    <section className="pres-panel" aria-label="Presupuestos">
      <div className="odonto-cabecera">
        <h3>Presupuestos</h3>
        {esOdontologo && modo.tipo !== "nuevo" && (
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={!hayHallazgosActivos}
            onClick={(): void => {
              setAviso(null);
              setModo({ tipo: "nuevo" });
            }}
          >
            Nuevo presupuesto
          </button>
        )}
      </div>
      {esOdontologo && !hayHallazgosActivos && (
        <p className="muted">Para armar un presupuesto hacen falta hallazgos activos en el odontograma.</p>
      )}

      {aviso !== null && (
        <p role="alert" className="banner banner-error">
          {aviso}
        </p>
      )}

      {modo.tipo === "nuevo" && (
        <PresupuestoForm
          idBase="nuevo"
          hallazgos={hallazgos}
          nombres={nombres}
          tratamientos={tratamientos}
          etiquetaBoton="Guardar presupuesto"
          alCancelar={(): void => setModo({ tipo: "ver" })}
          alEnviar={async (items): Promise<Presupuesto> => {
            const creado = await crearPresupuesto(pacienteId, items);
            aplicar(creado);
            setModo({ tipo: "ver" });
            return creado;
          }}
        />
      )}

      {lista.length === 0 ? (
        <p className="muted">El paciente no tiene presupuestos.</p>
      ) : (
        <ul className="pres-lista" aria-label="Lista de presupuestos">
          {lista.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                className="pres-fila"
                aria-pressed={p.id === seleccionadoId}
                onClick={(): void => {
                  setSeleccionadoId(p.id);
                  setModo({ tipo: "ver" });
                  setAviso(null);
                }}
              >
                <span>Presupuesto {p.id}</span>
                <span className="badge" data-pres={p.estado}>
                  {ETIQUETA_ESTADO[p.estado]}
                </span>
                <span className="pres-importe">{formatearMoneda(p.total)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {seleccionado !== null && (
        <PresupuestoDetalle presupuesto={seleccionado}>{acciones(seleccionado)}</PresupuestoDetalle>
      )}
    </section>
  );
}

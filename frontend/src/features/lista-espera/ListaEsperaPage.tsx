import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "../../shared/api-client";
import { convertirEntrada, darDeBaja, listarEspera, ofrecerHueco } from "./api";
import { Countdown, useAhoraMs } from "./Countdown";
import { ETIQUETA_ESTADO, ordenarFifo } from "./tipos";
import type { EntradaEspera } from "./tipos";

type Accion = { id: number; tipo: "ofrecer" | "baja" };

function mensajeDe(error: unknown): string {
  if (error instanceof ApiError) {
    return error.httpStatus === 0 ? "No hay conexión con el servidor." : error.message;
  }
  return "No se pudo completar la acción.";
}

function destinoDe(entrada: EntradaEspera): string {
  if (entrada.profesional_id !== null) return `Profesional #${entrada.profesional_id}`;
  return entrada.especialidad ?? "Sin destino";
}

interface OfrecerFormProps {
  entrada: EntradaEspera;
  alTerminar: () => void;
  alCancelar: () => void;
}

function OfrecerForm({ entrada, alTerminar, alCancelar }: OfrecerFormProps): JSX.Element {
  const [profesional, setProfesional] = useState<string>(String(entrada.profesional_id ?? ""));
  const [sillon, setSillon] = useState<string>("");
  const [inicio, setInicio] = useState<string>("");
  const [fin, setFin] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<boolean>(false);

  async function enviar(evento: FormEvent): Promise<void> {
    evento.preventDefault();
    if (profesional === "" || sillon === "" || inicio === "" || fin === "") {
      setError("Completá profesional, sillón, inicio y fin del hueco.");
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      await ofrecerHueco(entrada.id, {
        profesional_id: Number(profesional),
        sillon_id: Number(sillon),
        inicio: new Date(inicio).toISOString(),
        fin: new Date(fin).toISOString(),
      });
      alTerminar();
    } catch (e) {
      setError(mensajeDe(e));
      setEnviando(false);
    }
  }

  return (
    <form className="espera-form" onSubmit={(e): void => void enviar(e)}>
      <div className="field">
        <label htmlFor={`prof-${entrada.id}`}>Profesional (ID)</label>
        <input
          id={`prof-${entrada.id}`}
          className="input"
          type="number"
          value={profesional}
          onChange={(e): void => setProfesional(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor={`sillon-${entrada.id}`}>Sillón (ID)</label>
        <input
          id={`sillon-${entrada.id}`}
          className="input"
          type="number"
          value={sillon}
          onChange={(e): void => setSillon(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor={`inicio-${entrada.id}`}>Inicio del hueco</label>
        <input
          id={`inicio-${entrada.id}`}
          className="input"
          type="datetime-local"
          value={inicio}
          onChange={(e): void => setInicio(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor={`fin-${entrada.id}`}>Fin del hueco</label>
        <input
          id={`fin-${entrada.id}`}
          className="input"
          type="datetime-local"
          value={fin}
          onChange={(e): void => setFin(e.target.value)}
        />
      </div>
      {error !== null && (
        <p className="error-msg" role="alert">
          {error}
        </p>
      )}
      <div className="row">
        <button className="btn btn-primary btn-sm" type="submit" disabled={enviando}>
          Enviar oferta
        </button>
        <button className="btn btn-ghost btn-sm" type="button" onClick={alCancelar}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

interface BajaFormProps {
  entrada: EntradaEspera;
  alTerminar: () => void;
  alCancelar: () => void;
}

function BajaForm({ entrada, alTerminar, alCancelar }: BajaFormProps): JSX.Element {
  const [motivo, setMotivo] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<boolean>(false);

  async function confirmar(evento: FormEvent): Promise<void> {
    evento.preventDefault();
    if (motivo.trim() === "") {
      setError("Ingresá el motivo de la baja.");
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      await darDeBaja(entrada.id, motivo.trim());
      alTerminar();
    } catch (e) {
      setError(mensajeDe(e));
      setEnviando(false);
    }
  }

  return (
    <form className="espera-form" onSubmit={(e): void => void confirmar(e)}>
      <div className="field">
        <label htmlFor={`motivo-${entrada.id}`}>Motivo de la baja</label>
        <textarea
          id={`motivo-${entrada.id}`}
          className="input"
          maxLength={200}
          value={motivo}
          aria-invalid={error !== null}
          onChange={(e): void => setMotivo(e.target.value)}
        />
      </div>
      {error !== null && (
        <p className="error-msg" role="alert">
          {error}
        </p>
      )}
      <div className="row">
        <button className="btn btn-danger btn-sm" type="submit" disabled={enviando}>
          Confirmar baja
        </button>
        <button className="btn btn-ghost btn-sm" type="button" onClick={alCancelar}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

interface ItemProps {
  entrada: EntradaEspera;
  ahoraMs: number;
  accion: Accion | null;
  alElegir: (accion: Accion | null) => void;
  alConvertir: (id: number) => void;
  alRefrescar: () => void;
}

function EntradaItem({ entrada, ahoraMs, accion, alElegir, alConvertir, alRefrescar }: ItemProps): JSX.Element {
  const abierta = accion?.id === entrada.id ? accion.tipo : null;
  const resuelta = entrada.estado === "convertida" || entrada.estado === "vencida";
  return (
    <li data-espera-id={entrada.id}>
      <span className="quien">Paciente #{entrada.paciente_id}</span>
      <span className="row">
        {entrada.estado === "activa" && (
          <button
            className="btn btn-primary btn-sm"
            type="button"
            onClick={(): void => alElegir({ id: entrada.id, tipo: "ofrecer" })}
          >
            Ofrecer hueco
          </button>
        )}
        {entrada.estado === "ofrecida" && (
          <button className="btn btn-secondary btn-sm" type="button" onClick={(): void => alConvertir(entrada.id)}>
            Convertir en turno
          </button>
        )}
        {!resuelta && (
          <button
            className="btn btn-ghost btn-sm"
            type="button"
            onClick={(): void => alElegir({ id: entrada.id, tipo: "baja" })}
          >
            Dar de baja
          </button>
        )}
      </span>
      <span className="detalle">
        <span className="badge" data-espera={entrada.estado}>
          {ETIQUETA_ESTADO[entrada.estado]}
        </span>
        {entrada.estado === "ofrecida" && entrada.oferta_expira_en !== null && (
          <span>
            Vence en <Countdown expiraEn={entrada.oferta_expira_en} ahoraMs={ahoraMs} />
          </span>
        )}
        {entrada.estado === "vencida" && entrada.motivo_baja !== null && <span>{entrada.motivo_baja}</span>}
        <span>{destinoDe(entrada)}</span>
      </span>
      {abierta === "ofrecer" && (
        <OfrecerForm
          entrada={entrada}
          alCancelar={(): void => alElegir(null)}
          alTerminar={(): void => {
            alElegir(null);
            alRefrescar();
          }}
        />
      )}
      {abierta === "baja" && (
        <BajaForm
          entrada={entrada}
          alCancelar={(): void => alElegir(null)}
          alTerminar={(): void => {
            alElegir(null);
            alRefrescar();
          }}
        />
      )}
    </li>
  );
}

/** Cola FIFO de lista de espera para secretaría|admin (C-07). */
export function ListaEsperaPage(): JSX.Element {
  const [entradas, setEntradas] = useState<EntradaEspera[]>([]);
  const [cargando, setCargando] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [accion, setAccion] = useState<Accion | null>(null);

  const hayOfertas = entradas.some((e) => e.estado === "ofrecida");
  const ahoraMs = useAhoraMs(hayOfertas);

  const cargar = useCallback((): void => {
    listarEspera()
      .then((lista) => {
        setEntradas(ordenarFifo(lista));
        setError(null);
      })
      .catch((e: unknown) => setError(mensajeDe(e)))
      .finally(() => setCargando(false));
  }, []);

  useEffect(cargar, [cargar]);

  function convertir(id: number): void {
    convertirEntrada(id)
      .then(cargar)
      .catch((e: unknown) => setError(mensajeDe(e)));
  }

  return (
    <section className="wrap-espera">
      <h1>Lista de espera</h1>
      {error !== null && accion === null && (
        <p className="error-msg" role="alert">
          {error}
        </p>
      )}
      {cargando && <p>Cargando…</p>}
      {!cargando && entradas.length === 0 && error === null && (
        <p className="muted">No hay nadie en la lista de espera.</p>
      )}
      {entradas.length > 0 && (
        <ul className="cola" aria-label="Lista de espera">
          {entradas.map((entrada) => (
            <EntradaItem
              key={entrada.id}
              entrada={entrada}
              ahoraMs={ahoraMs}
              accion={accion}
              alElegir={setAccion}
              alConvertir={convertir}
              alRefrescar={cargar}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

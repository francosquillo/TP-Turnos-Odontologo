import { useCallback, useEffect, useState } from "react";
import type { DragEvent } from "react";
import {
  ConflictoHuecoError,
  cambiarEstadoTurno,
  crearTurno,
  listarAgenda,
  reprogramarTurno,
} from "./api";
import type { CrearTurnoDatos } from "./api";
import { CancelarModal } from "./CancelarModal";
import { CrearForm } from "./CrearForm";
import { ReprogramarZona } from "./ReprogramarZona";
import { TurnoCard } from "./TurnoCard";
import type { Hueco, TurnoAgenda, VistaAgenda } from "./tipos";
import { claveDia, formatoHora } from "./tipos";

/**
 * PATCH /turnos/... devuelve TurnoOut (sin nombres): se conservan los de la fila previa
 * salvo que la respuesta los traiga.
 */
function fusionar(previo: TurnoAgenda, actualizado: TurnoAgenda): TurnoAgenda {
  return {
    ...previo,
    ...actualizado,
    paciente_nombre: actualizado.paciente_nombre ?? previo.paciente_nombre,
    profesional_matricula: actualizado.profesional_matricula ?? previo.profesional_matricula,
    sillon_nombre: actualizado.sillon_nombre ?? previo.sillon_nombre,
  };
}

function hoyLocal(): string {
  return claveDia(new Date().toISOString());
}

interface Props {
  /** C-08: abre el odontograma del paciente del turno (odontologo y secretaria). */
  alAbrirOdontograma?: (turno: TurnoAgenda) => void;
  /** C-09: abre la cuenta corriente del paciente del turno (secretaria y admin). */
  alAbrirCuenta?: (turno: TurnoAgenda) => void;
}

export function AgendaPage({ alAbrirOdontograma, alAbrirCuenta }: Props = {}): JSX.Element {
  const [vista, setVista] = useState<VistaAgenda>("dia");
  const [fecha, setFecha] = useState<string>(hoyLocal());
  const [turnos, setTurnos] = useState<TurnoAgenda[]>([]);
  const [aviso, setAviso] = useState<string | null>(null);
  const [alternativas, setAlternativas] = useState<Hueco[]>([]);
  const [aCancelar, setACancelar] = useState<TurnoAgenda | null>(null);
  const [nuevoHorario, setNuevoHorario] = useState<string>("");

  useEffect(() => {
    let vigente = true;
    listarAgenda(vista, fecha)
      .then((filas) => {
        if (vigente) {
          setTurnos(filas);
          setAviso(null);
          setAlternativas([]);
        }
      })
      .catch(() => {
        if (vigente) setAviso("No se pudo cargar la agenda");
      });
    return (): void => {
      vigente = false;
    };
  }, [vista, fecha]);

  const alConfirmar = useCallback(async (turno: TurnoAgenda): Promise<void> => {
    const actualizado = await cambiarEstadoTurno(turno.id, "confirmado", null);
    setTurnos((prev) => prev.map((t) => (t.id === turno.id ? fusionar(t, actualizado) : t)));
  }, []);

  const alCancelar = useCallback(
    async (motivo: string): Promise<void> => {
      if (aCancelar === null) return;
      const actualizado = await cambiarEstadoTurno(aCancelar.id, "cancelado", motivo);
      setTurnos((prev) => prev.map((t) => (t.id === aCancelar.id ? fusionar(t, actualizado) : t)));
      setACancelar(null);
    },
    [aCancelar],
  );

  const alMarcar = useCallback(
    async (turno: TurnoAgenda, estado: "asistido" | "ausente"): Promise<void> => {
      const actualizado = await cambiarEstadoTurno(turno.id, estado, null);
      setTurnos((prev) => prev.map((t) => (t.id === turno.id ? fusionar(t, actualizado) : t)));
    },
    [],
  );

  const alCrear = useCallback(async (datos: CrearTurnoDatos): Promise<void> => {
    try {
      const nuevo = await crearTurno(datos);
      setTurnos((prev) => [...prev, nuevo]);
      setAlternativas([]);
      setAviso(null);
    } catch (error) {
      if (error instanceof ConflictoHuecoError) {
        setAlternativas(error.alternativas);
        setAviso("hueco ocupado: elegí una alternativa");
      } else {
        setAviso("No se pudo crear el turno");
      }
    }
  }, []);

  const alIniciarArrastre = useCallback((_id: number, e: DragEvent): void => {
    e.dataTransfer.setData("text/plain", String(_id));
  }, []);

  const alSoltar = useCallback(
    async (e: DragEvent): Promise<void> => {
      e.preventDefault();
      if (nuevoHorario === "") return;
      const id = Number(e.dataTransfer.getData("text/plain"));
      const objetivo = turnos.find((t) => t.id === id);
      if (objetivo === undefined) return;
      const duracionMs =
        new Date(objetivo.fin).getTime() - new Date(objetivo.inicio).getTime();
      const inicio = new Date(nuevoHorario).toISOString();
      const fin = new Date(new Date(nuevoHorario).getTime() + duracionMs).toISOString();
      const previo = turnos;
      // Optimista con rollback ante 409 (D-08).
      setTurnos((curr) =>
        curr.map((t) => (t.id === id ? { ...t, inicio, fin } : t)),
      );
      try {
        const actualizado = await reprogramarTurno(id, inicio, fin);
        setTurnos((curr) => curr.map((t) => (t.id === id ? fusionar(t, actualizado) : t)));
        setAlternativas([]);
        setAviso(null);
      } catch (error) {
        setTurnos(previo);
        if (error instanceof ConflictoHuecoError) {
          setAlternativas(error.alternativas);
          setAviso("hueco ocupado: el turno vuelve a su horario original");
        } else {
          setAviso("No se pudo reprogramar");
        }
      }
    },
    [nuevoHorario, turnos],
  );

  const porDia = new Map<string, TurnoAgenda[]>();
  for (const turno of turnos) {
    const clave = claveDia(turno.inicio);
    const lista = porDia.get(clave) ?? [];
    lista.push(turno);
    porDia.set(clave, lista);
  }

  return (
    <section aria-label="Agenda" style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-2)" }}>
        <h2 style={{ margin: 0 }}>Agenda</h2>
        <span className="muted" style={{ fontVariantNumeric: "tabular-nums" }}>
          {turnos.length} turno(s) en vista
        </span>
      </div>

      <nav className="card row" style={{ padding: "var(--space-3)", gap: "var(--space-2)" }}>
        <button
          type="button"
          className={`btn ${vista === "dia" ? "btn-primary" : "btn-secondary"} btn-sm`}
          onClick={(): void => setVista("dia")}
        >
          Día
        </button>
        <button
          type="button"
          className={`btn ${vista === "semana" ? "btn-primary" : "btn-secondary"} btn-sm`}
          onClick={(): void => setVista("semana")}
        >
          Semana
        </button>
        <button
          type="button"
          className={`btn ${vista === "mes" ? "btn-primary" : "btn-secondary"} btn-sm`}
          onClick={(): void => setVista("mes")}
        >
          Mes
        </button>
        <div className="row" style={{ marginLeft: "auto", gap: "var(--space-2)" }}>
          <label htmlFor="fecha-agenda" style={{ fontSize: "var(--text-sm)", fontWeight: "var(--weight-medium)" }}>
            Fecha
          </label>
          <input
            id="fecha-agenda"
            className="input"
            style={{ width: "auto", minHeight: "2rem", padding: "0 var(--space-2)" }}
            type="date"
            value={fecha}
            onChange={(e): void => setFecha(e.target.value)}
          />
        </div>
      </nav>

      {aviso !== null && (
        <div className="banner banner-warning">
          <p role="alert" style={{ margin: 0 }}>{aviso}</p>
        </div>
      )}

      {alternativas.length > 0 && (
        <div className="card">
          <h4 style={{ margin: "0 0 var(--space-2)" }}>Alternativas disponibles:</h4>
          <ul aria-label="Alternativas" style={{ margin: 0, paddingLeft: "var(--space-4)" }}>
            {alternativas.map((h) => (
              <li key={h.inicio}>
                {formatoHora(h.inicio)}–{formatoHora(h.fin)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {vista === "mes" ? (
        <ul className="grid" style={{ listStyle: "none", padding: 0 }}>
          {[...porDia.entries()].map(([dia, lista]) => (
            <li key={dia}>
              <button
                type="button"
                className="card btn btn-secondary"
                style={{ width: "100%", justifyContent: "space-between", height: "auto", padding: "var(--space-4)" }}
                onClick={(): void => {
                  setFecha(dia);
                  setVista("dia");
                }}
              >
                <span>{dia}</span>
                <span className="badge">{lista.length} turnos</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="grid">
          {turnos.map((turno) => (
            <TurnoCard
              key={turno.id}
              turno={turno}
              alIniciarArrastre={alIniciarArrastre}
              alCancelar={setACancelar}
              alConfirmar={(t): void => {
                void alConfirmar(t);
              }}
              alMarcar={(t, estado): void => {
                void alMarcar(t, estado);
              }}
              {...(alAbrirOdontograma === undefined ? {} : { alAbrirOdontograma })}
              {...(alAbrirCuenta === undefined ? {} : { alAbrirCuenta })}
            />
          ))}
        </div>
      )}

      <ReprogramarZona
        nuevoHorario={nuevoHorario}
        alCambiarHorario={setNuevoHorario}
        alSoltar={(e): void => {
          void alSoltar(e);
        }}
      />

      <CrearForm
        alCrear={(datos): void => {
          void alCrear(datos);
        }}
      />

      {aCancelar !== null && (
        <CancelarModal
          turno={aCancelar}
          alCerrar={(): void => setACancelar(null)}
          alConfirmar={(motivo): void => {
            void alCancelar(motivo);
          }}
        />
      )}
    </section>
  );
}

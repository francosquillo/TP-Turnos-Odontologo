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

function hoyLocal(): string {
  return new Date().toISOString().slice(0, 10);
}

export function AgendaPage(): JSX.Element {
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
    setTurnos((prev) => prev.map((t) => (t.id === turno.id ? actualizado : t)));
  }, []);

  const alCancelar = useCallback(
    async (motivo: string): Promise<void> => {
      if (aCancelar === null) return;
      const actualizado = await cambiarEstadoTurno(aCancelar.id, "cancelado", motivo);
      setTurnos((prev) => prev.map((t) => (t.id === aCancelar.id ? actualizado : t)));
      setACancelar(null);
    },
    [aCancelar],
  );

  const alMarcar = useCallback(
    async (turno: TurnoAgenda, estado: "asistido" | "ausente"): Promise<void> => {
      const actualizado = await cambiarEstadoTurno(turno.id, estado, null);
      setTurnos((prev) => prev.map((t) => (t.id === turno.id ? actualizado : t)));
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
        setTurnos((curr) => curr.map((t) => (t.id === id ? actualizado : t)));
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
    <section aria-label="Agenda">
      <h2>Agenda</h2>
      <nav>
        <button type="button" onClick={(): void => setVista("dia")}>
          Día
        </button>
        <button type="button" onClick={(): void => setVista("semana")}>
          Semana
        </button>
        <button type="button" onClick={(): void => setVista("mes")}>
          Mes
        </button>
        <label htmlFor="fecha-agenda">Fecha</label>
        <input
          id="fecha-agenda"
          type="date"
          value={fecha}
          onChange={(e): void => setFecha(e.target.value)}
        />
      </nav>
      {aviso !== null && <p role="alert">{aviso}</p>}
      {alternativas.length > 0 && (
        <ul aria-label="Alternativas">
          {alternativas.map((h) => (
            <li key={h.inicio}>
              {formatoHora(h.inicio)}–{formatoHora(h.fin)}
            </li>
          ))}
        </ul>
      )}
      {vista === "mes" ? (
        <ul>
          {[...porDia.entries()].map(([dia, lista]) => (
            <li key={dia}>
              <button
                type="button"
                onClick={(): void => {
                  setFecha(dia);
                  setVista("dia");
                }}
              >
                {dia}: {lista.length} turnos
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div>
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

import type { DragEvent } from "react";
import type { TurnoAgenda } from "./tipos";
import { COLOR_POR_ESTADO, formatoHora } from "./tipos";

interface Props {
  turno: TurnoAgenda;
  alIniciarArrastre: (id: number, e: DragEvent) => void;
  alCancelar: (turno: TurnoAgenda) => void;
  alConfirmar: (turno: TurnoAgenda) => void;
  alMarcar: (turno: TurnoAgenda, estado: "asistido" | "ausente") => void;
}

export function TurnoCard({
  turno,
  alIniciarArrastre,
  alCancelar,
  alConfirmar,
  alMarcar,
}: Props): JSX.Element {
  return (
    <article
      draggable
      data-estado={turno.estado}
      style={{ borderLeft: `6px solid ${COLOR_POR_ESTADO[turno.estado]}` }}
      onDragStart={(e: DragEvent): void => alIniciarArrastre(turno.id, e)}
    >
      <header>
        <strong>{turno.paciente_nombre ?? `Paciente ${turno.paciente_id}`}</strong>
        <span>
          {formatoHora(turno.inicio)}–{formatoHora(turno.fin)}
        </span>
      </header>
      <p>
        {turno.estado} · {turno.sillon_nombre ?? `Sillón ${turno.sillon_id}`}
      </p>
      <div>
        {turno.estado === "pendiente" && (
          <button type="button" onClick={(): void => alConfirmar(turno)}>
            Confirmar
          </button>
        )}
        {(turno.estado === "pendiente" || turno.estado === "confirmado") && (
          <button type="button" onClick={(): void => alCancelar(turno)}>
            Cancelar
          </button>
        )}
        {turno.estado === "confirmado" && (
          <>
            <button
              type="button"
              onClick={(): void => alMarcar(turno, "asistido")}
            >
              Asistido
            </button>
            <button type="button" onClick={(): void => alMarcar(turno, "ausente")}>
              Ausente
            </button>
          </>
        )}
      </div>
    </article>
  );
}

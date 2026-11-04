import type { DragEvent } from "react";
import type { TurnoAgenda } from "./tipos";
import { COLOR_POR_ESTADO, formatoHora } from "./tipos";

interface Props {
  turno: TurnoAgenda;
  alIniciarArrastre: (id: number, e: DragEvent) => void;
  alCancelar: (turno: TurnoAgenda) => void;
  alConfirmar: (turno: TurnoAgenda) => void;
  alMarcar: (turno: TurnoAgenda, estado: "asistido" | "ausente") => void;
  /** C-08: solo odontologo y secretaria lo reciben; sin esta funcion no hay acceso. */
  alAbrirOdontograma?: (turno: TurnoAgenda) => void;
  /** C-09: solo secretaria y admin lo reciben; sin esta funcion no hay acceso a la cuenta. */
  alAbrirCuenta?: (turno: TurnoAgenda) => void;
}

export function TurnoCard({
  turno,
  alIniciarArrastre,
  alCancelar,
  alConfirmar,
  alMarcar,
  alAbrirOdontograma,
  alAbrirCuenta,
}: Props): JSX.Element {
  return (
    <article
      className="card"
      draggable
      data-estado={turno.estado}
      style={{
        borderLeft: `6px solid ${COLOR_POR_ESTADO[turno.estado]}`,
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-2)",
        transition: "transform var(--motion-fast) var(--ease-out), box-shadow var(--motion-fast) var(--ease-out)",
      }}
      onDragStart={(e: DragEvent): void => alIniciarArrastre(turno.id, e)}
    >
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "var(--space-2)" }}>
        <strong style={{ fontSize: "var(--text-md)" }}>
          {turno.paciente_nombre ?? `Paciente ${turno.paciente_id}`}
        </strong>
        <span className="muted" style={{ fontVariantNumeric: "tabular-nums", fontWeight: "var(--weight-medium)" }}>
          {formatoHora(turno.inicio)}–{formatoHora(turno.fin)}
        </span>
      </header>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
        <span className="badge" data-estado={turno.estado}>
          {turno.estado}
        </span>
        <p style={{ margin: 0, fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
          {turno.estado} · {turno.sillon_nombre ?? `Sillón ${turno.sillon_id}`}
        </p>
      </div>
      <div className="row" style={{ marginTop: "var(--space-2)", gap: "var(--space-2)" }}>
        {turno.estado === "pendiente" && (
          <button type="button" className="btn btn-primary btn-sm" onClick={(): void => alConfirmar(turno)}>
            Confirmar
          </button>
        )}
        {(turno.estado === "pendiente" || turno.estado === "confirmado") && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={(): void => alCancelar(turno)}>
            Cancelar
          </button>
        )}
        {alAbrirOdontograma !== undefined && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={(): void => alAbrirOdontograma(turno)}>
            Odontograma
          </button>
        )}
        {alAbrirCuenta !== undefined && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={(): void => alAbrirCuenta(turno)}>
            Cuenta corriente
          </button>
        )}
        {turno.estado === "confirmado" && (
          <>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={(): void => alMarcar(turno, "asistido")}
            >
              Asistido
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={(): void => alMarcar(turno, "ausente")}
            >
              Ausente
            </button>
          </>
        )}
      </div>
    </article>
  );
}

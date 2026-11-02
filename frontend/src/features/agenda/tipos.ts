/** Tipos agenda C-04 (D-08): tipado estricto, cero `any`. */
import { claveDiaAR, horaAR } from "../../shared/fecha";

export type EstadoTurno =
  | "pendiente"
  | "confirmado"
  | "asistido"
  | "ausente"
  | "cancelado";

export type VistaAgenda = "dia" | "semana" | "mes";

export interface TurnoAgenda {
  id: number;
  inicio: string;
  fin: string;
  estado: EstadoTurno;
  paciente_id: number;
  paciente_nombre: string | null;
  profesional_id: number;
  profesional_matricula: string | null;
  sillon_id: number;
  sillon_nombre: string | null;
}

export interface Hueco {
  inicio: string;
  fin: string;
}

export const COLOR_POR_ESTADO: Record<EstadoTurno, string> = {
  pendiente: "#b45309",
  confirmado: "#1d4ed8",
  asistido: "#15803d",
  ausente: "#6b7280",
  cancelado: "#b91c1c",
};

/** HH:MM en America/Argentina/Buenos_Aires (determinista, sin depender de la TZ local). */
export function formatoHora(iso: string): string {
  return horaAR(iso);
}

/** YYYY-MM-DD del día argentino para agrupar por día. */
export function claveDia(iso: string): string {
  return claveDiaAR(iso);
}

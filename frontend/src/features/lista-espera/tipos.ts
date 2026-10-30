/** Tipos y helpers puros de lista de espera (C-07). Cero `any`. */

export type EstadoEspera = "activa" | "ofrecida" | "convertida" | "vencida";

export interface EntradaEspera {
  id: number;
  paciente_id: number;
  profesional_id: number | null;
  especialidad: string | null;
  preferencia_horaria: Record<string, unknown> | null;
  estado: EstadoEspera;
  oferta_expira_en: string | null;
  oferta_hueco: Record<string, unknown> | null;
  motivo_baja: string | null;
  created_at: string;
}

export interface HuecoOferta {
  profesional_id: number;
  sillon_id: number;
  inicio: string;
  fin: string;
}

export interface OfertaPublica {
  nombre_pila: string;
  inicio: string;
  fin: string;
  oferta_expira_en: string;
}

export const ETIQUETA_ESTADO: Record<EstadoEspera, string> = {
  activa: "Activa",
  ofrecida: "Ofrecida",
  convertida: "Convertida",
  vencida: "Vencida",
};

/** Menos de este margen el countdown se marca urgente (5 min). */
export const SEGUNDOS_URGENTE = 300;

/** FIFO: created_at ascendente (copia, no muta). */
export function ordenarFifo(entradas: EntradaEspera[]): EntradaEspera[] {
  return [...entradas].sort(
    (a, b) => Date.parse(a.created_at) - Date.parse(b.created_at) || a.id - b.id,
  );
}

/** Segundos restantes hasta `expiraEn` desde `ahoraMs`; nunca negativo. */
export function segundosRestantes(expiraEn: string, ahoraMs: number): number {
  return Math.max(0, Math.ceil((Date.parse(expiraEn) - ahoraMs) / 1000));
}

export function formatearCuenta(segundos: number): string {
  const dos = (n: number): string => String(n).padStart(2, "0");
  const h = Math.floor(segundos / 3600);
  const m = Math.floor((segundos % 3600) / 60);
  return `${dos(h)}:${dos(m)}:${dos(segundos % 60)}`;
}

export function formatoFechaHora(iso: string): string {
  return new Intl.DateTimeFormat("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Argentina/Buenos_Aires",
  }).format(new Date(iso));
}

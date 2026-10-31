/** Tipos del feature de presupuestos (C-09, D-21). Los importes son TEXTO decimal. */
import type { Cara } from "../odontograma/tipos";

export type EstadoPresupuesto = "borrador" | "presentado" | "aceptado" | "rechazado" | "cobrado";

export const ESTADOS_PRESUPUESTO: readonly EstadoPresupuesto[] = [
  "borrador",
  "presentado",
  "aceptado",
  "rechazado",
  "cobrado",
];

export const ETIQUETA_ESTADO: Record<EstadoPresupuesto, string> = {
  borrador: "Borrador",
  presentado: "Presentado",
  aceptado: "Aceptado",
  rechazado: "Rechazado",
  cobrado: "Cobrado",
};

export interface ItemPresupuesto {
  id: number;
  hallazgo_id: number;
  tratamiento_id: number;
  tratamiento_nombre: string;
  /** `null` para el admin (vista financiera: sin datos clínicos). */
  pieza_fdi: number | null;
  cara: Cara | null;
  cantidad: number;
  /** Texto decimal copiado del catálogo por el servidor. */
  precio: string;
  subtotal: string;
  /** `false` si el hallazgo se corrigió o se dio de baja después de presupuestar. */
  hallazgo_vigente: boolean;
}

export interface Presupuesto {
  id: number;
  paciente_id: number;
  profesional_id: number;
  estado: EstadoPresupuesto;
  /** Lo calcula siempre el servidor; el cliente no suma importes. */
  total: string;
  /** `null` para el admin. */
  motivo_rechazo: string | null;
  presentado_at: string | null;
  decidido_at: string | null;
  created_at: string;
  updated_at: string;
  /** El cargo del presupuesto aceptado fue anulado (el estado no cambia). */
  cargo_anulado: boolean;
  /** Quien consulta es el autor: solo el autor presenta, acepta, rechaza o edita. */
  es_propio: boolean;
  items: ItemPresupuesto[];
}

export interface ItemEntrada {
  hallazgo_id: number;
  tratamiento_id: number;
  cantidad: number;
}

export interface Tratamiento {
  id: number;
  codigo: string;
  codigo_nomenclador: string | null;
  nombre: string;
  precio_base: string;
}

export function esEstadoPresupuesto(valor: unknown): valor is EstadoPresupuesto {
  return typeof valor === "string" && (ESTADOS_PRESUPUESTO as readonly string[]).includes(valor);
}

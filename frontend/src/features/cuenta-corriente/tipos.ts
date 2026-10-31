/** Tipos del feature de cuenta corriente (C-09, D-21). Los importes son TEXTO decimal. */

export type TipoMovimiento = "cargo" | "pago" | "ajuste";

export const TIPOS_MOVIMIENTO: readonly TipoMovimiento[] = ["cargo", "pago", "ajuste"];

export const ETIQUETA_TIPO: Record<TipoMovimiento, string> = {
  cargo: "Cargo",
  pago: "Pago",
  ajuste: "Anulación / ajuste",
};

export interface Movimiento {
  id: number;
  tipo: TipoMovimiento;
  /** Texto decimal con signo: cargo positivo, pago negativo, ajuste distinto de cero. */
  monto: string;
  concepto: string;
  motivo: string | null;
  turno_id: number | null;
  presupuesto_id: number | null;
  recibo_id: number | null;
  /** Si es un contramovimiento, el cargo que anula. */
  anula_a_id: number | null;
  creado_por: number;
  created_at: string;
  /** El movimiento tiene un contramovimiento. */
  anulado: boolean;
}

export interface Cuenta {
  paciente_id: number;
  /** Derivado por el servidor (suma de movimientos); positivo = deuda del paciente. */
  saldo: string;
  movimientos: Movimiento[];
}

export function esTipoMovimiento(valor: unknown): valor is TipoMovimiento {
  return typeof valor === "string" && (TIPOS_MOVIMIENTO as readonly string[]).includes(valor);
}

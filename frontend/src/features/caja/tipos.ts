/** Tipos del feature de caja y recibos (C-10, D-17, D-24, D-25). Los importes son TEXTO decimal.
 *
 * El cliente no hace aritmetica de dinero: totales, desglose y diferencia los calcula el
 * servidor. Las fechas operativas llegan como `YYYY-MM-DD` y se formatean cortando el texto.
 */

export type Medio = "efectivo" | "transferencia" | "tarjeta_simulada";

export const MEDIOS: readonly Medio[] = ["efectivo", "transferencia", "tarjeta_simulada"];

export const ETIQUETA_MEDIO: Record<Medio, string> = {
  efectivo: "Efectivo",
  transferencia: "Transferencia",
  tarjeta_simulada: "Tarjeta (simulada)",
};

export type Bloqueo = "caja_pendiente" | "caja_cerrada";
export type EstadoDeCaja = "abierta" | "cerrada";

export interface Caja {
  id: number;
  /** `YYYY-MM-DD`, dia operativo en Buenos Aires. */
  fecha: string;
  estado: EstadoDeCaja;
  abierta_por: number;
  /** En una caja abierta lo calcula el servidor en cada lectura. */
  total_sistema: string;
  total_contado: string | null;
  diferencia: string | null;
  motivo_diferencia: string | null;
  cerrada_por: number | null;
  cerrada_at: string | null;
}

export interface DesgloseMedio {
  medio: Medio;
  subtotal: string;
}

/** Ingreso (o reversion, con monto negativo) de una liquidacion de obra social (C-11, D-15).
 * No lleva datos de pacientes: la secretaria tambien ve la caja. */
export interface IngresoLiquidacion {
  liquidacion_id: number;
  obra_social: string;
  /** `YYYY-MM-DD`, siempre el dia 1 del mes liquidado. */
  periodo: string;
  medio: Medio;
  monto: string;
  created_at: string;
}

export interface EstadoCaja {
  fecha: string;
  hoy: string;
  operable: boolean;
  bloqueo: Bloqueo | null;
  caja: Caja | null;
  desglose: DesgloseMedio[];
  ingresos_liquidacion: IngresoLiquidacion[];
}

export interface Recibo {
  id: number;
  numero: number;
  paciente_id: number;
  paciente_nombre: string;
  monto: string;
  medio: Medio;
  fecha: string;
  emitido_por: number;
  created_at: string;
  anulado: boolean;
  motivo_anulacion: string | null;
  anulado_por: number | null;
  anulado_at: string | null;
}

export interface Cobro extends Recibo {
  presupuesto_id: number;
  presupuesto_estado: string;
}

export interface DatosCobro {
  presupuesto_id: number;
  monto: string;
  medio: Medio;
  /** UUID v4 en minusculas generado por el cliente (D-25); nunca se muestra ni se loguea. */
  clave_idempotencia: string;
}

export interface DatosCierre {
  caja_id: number;
  total_contado: string;
  motivo_diferencia?: string;
}

export function esMedio(valor: unknown): valor is Medio {
  return typeof valor === "string" && (MEDIOS as readonly string[]).includes(valor);
}

/** Decimal positivo con hasta dos cifras decimales, validado como TEXTO (nunca `number`). */
export function esImporteValido(texto: string): boolean {
  return /^\d+(\.\d{1,2})?$/.test(texto) && /[1-9]/.test(texto);
}

/** Importe no negativo (el contado puede ser 0), tambien validado como texto. */
export function esContadoValido(texto: string): boolean {
  return /^\d+(\.\d{1,2})?$/.test(texto);
}

const FECHA_ISO = /^(\d{4})-(\d{2})-(\d{2})/;

/** "2026-10-31" -> "31/10/2026" cortando el texto: `new Date("2026-10-31")` se lee como UTC y
 * en Argentina mostraria el dia anterior. */
export function formatearFecha(fecha: string): string {
  const partes = FECHA_ISO.exec(fecha);
  if (partes === null) return "—";
  return `${partes[3]}/${partes[2]}/${partes[1]}`;
}

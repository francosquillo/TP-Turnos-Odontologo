/** Tipos del feature de liquidaciones a obras sociales (C-11, D-09, D-12, D-13, D-16).
 *
 * Los importes son TEXTO decimal: el cliente no hace aritmetica de dinero. Totales,
 * subtotales y montos de fila los calcula el servidor. El periodo llega como `YYYY-MM-DD`
 * (siempre dia 1) y se formatea cortando el texto, nunca con `Date`.
 */

export type EstadoLiquidacion = "borrador" | "presentada" | "cobrada";

export const ESTADOS_LIQUIDACION: readonly EstadoLiquidacion[] = ["borrador", "presentada", "cobrada"];

export const ETIQUETA_ESTADO: Record<EstadoLiquidacion, string> = {
  borrador: "Borrador",
  presentada: "Presentada",
  cobrada: "Cobrada",
};

export interface ItemLiquidacion {
  id: number;
  item_presupuesto_id: number;
  /** `YYYY-MM-DD`, dia operativo de la aceptacion. */
  fecha_prestacion: string;
  paciente_nombre: string;
  codigo: string;
  descripcion: string;
  cantidad: number;
  monto: string;
  /** Sin arancel al aceptar: vale 0, no suma y queda para revision manual. */
  revision: boolean;
}

export interface PlanLiquidacion {
  plan_id: number;
  plan_nombre: string;
  subtotal: string;
  items: ItemLiquidacion[];
}

export interface Liquidacion {
  id: number;
  os_id: number;
  obra_social: string;
  /** `YYYY-MM-DD`, dia 1 del mes liquidado. */
  periodo: string;
  estado: EstadoLiquidacion;
  total: string;
  cantidad_items: number;
  cantidad_revision: number;
  creada_por: number;
  presentada_at: string | null;
  cobrada_at: string | null;
  cobro_revertido_at: string | null;
  created_at: string;
}

export interface LiquidacionDetalle extends Liquidacion {
  planes: PlanLiquidacion[];
  /** Tras revertir el cobro la liquidacion no se puede volver a cobrar (D-13). */
  revertida: boolean;
}

export interface ObraSocial {
  id: number;
  nombre: string;
  activa: boolean;
  created_at: string;
}

export interface DatosGenerar {
  os_id: number;
  /** `YYYY-MM`. */
  periodo: string;
}

export type FormatoInforme = "csv" | "pdf";

export function esEstadoLiquidacion(valor: unknown): valor is EstadoLiquidacion {
  return typeof valor === "string" && (ESTADOS_LIQUIDACION as readonly string[]).includes(valor);
}

/** Mes `YYYY-MM` valido (01 a 12), validado como texto. */
export function esPeriodoValido(texto: string): boolean {
  return /^\d{4}-(0[1-9]|1[0-2])$/.test(texto);
}

/** "2026-10-01" -> "10/2026" cortando el texto: `new Date` se leeria como UTC y correria el dia. */
export function periodoATexto(periodo: string): string {
  const partes = /^(\d{4})-(\d{2})/.exec(periodo);
  return partes === null ? "—" : `${partes[2]}/${partes[1]}`;
}

/** True si el importe decimal (texto) es mayor a cero, sin convertirlo a numero. */
export function esImportePositivo(texto: string): boolean {
  return /^\d+(\.\d+)?$/.test(texto) && /[1-9]/.test(texto);
}

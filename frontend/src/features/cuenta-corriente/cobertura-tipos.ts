/** Tipos de la cobertura de obra social en la cuenta corriente (C-11, D-04, D-07).
 *
 * Los importes son TEXTO decimal calculados por el servidor (`GET /validador-cobertura`): el
 * cliente no hace aritmetica de dinero ni recalcula el porcentaje.
 */

export type EstadoCobertura = "cubierto" | "sin_arancel" | "sin_plan";

export const ESTADOS_COBERTURA: readonly EstadoCobertura[] = ["cubierto", "sin_arancel", "sin_plan"];

export interface PlanPaciente {
  paciente_id: number;
  plan_id: number | null;
  plan_nombre: string | null;
  obra_social_id: number | null;
  obra_social_nombre: string | null;
}

export interface PlanDelCatalogo {
  id: number;
  obra_social_id: number;
  obra_social_nombre: string;
  nombre: string;
  activo: boolean;
  created_at: string;
}

export interface ValidadorCobertura {
  estado: EstadoCobertura;
  paciente_id: number;
  tratamiento_id: number;
  plan_id: number | null;
  precio: string;
  arancel: string | null;
  cubierto: string;
  a_cargo: string;
  /** Porcentaje cubierto con dos decimales, como texto ("70.00"). */
  porcentaje: string;
  fecha: string;
}

export function esEstadoCobertura(valor: unknown): valor is EstadoCobertura {
  return typeof valor === "string" && (ESTADOS_COBERTURA as readonly string[]).includes(valor);
}

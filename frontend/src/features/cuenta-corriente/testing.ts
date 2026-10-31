/** Fixtures compartidas por los tests de cuenta corriente (datos 100% ficticios). */
import type { Cuenta, Movimiento } from "./tipos";

let secuencia = 700;

export function movimiento(parcial: Partial<Movimiento> = {}): Movimiento {
  secuencia += 1;
  return {
    id: secuencia,
    tipo: "cargo",
    monto: "36000.00",
    concepto: "Presupuesto 31",
    motivo: null,
    turno_id: null,
    presupuesto_id: 31,
    recibo_id: null,
    anula_a_id: null,
    creado_por: 2,
    created_at: "2026-10-30T10:00:00Z",
    anulado: false,
    ...parcial,
  };
}

export function cuenta(parcial: Partial<Cuenta> = {}): Cuenta {
  return { paciente_id: 3, saldo: "36000.00", movimientos: [movimiento()], pendientes: [], ...parcial };
}

export function respuestaJson(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

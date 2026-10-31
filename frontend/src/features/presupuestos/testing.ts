/** Fixtures compartidas por los tests de presupuestos (datos 100% ficticios). */
import type { ItemPresupuesto, Presupuesto, Tratamiento } from "./tipos";

export const TRATAMIENTOS: Tratamiento[] = [
  { id: 1, codigo: "CON-001", codigo_nomenclador: null, nombre: "Consulta y diagnóstico", precio_base: "8000.00" },
  { id: 2, codigo: "OBT-001", codigo_nomenclador: null, nombre: "Obturación simple", precio_base: "18000.00" },
  { id: 3, codigo: "COR-001", codigo_nomenclador: null, nombre: "Corona de porcelana", precio_base: "120000.00" },
];

let secuencia = 500;

export function item(parcial: Partial<ItemPresupuesto> = {}): ItemPresupuesto {
  secuencia += 1;
  return {
    id: secuencia,
    hallazgo_id: 11,
    tratamiento_id: 2,
    tratamiento_nombre: "Obturación simple",
    pieza_fdi: 16,
    cara: "oclusal",
    cantidad: 2,
    precio: "18000.00",
    subtotal: "36000.00",
    hallazgo_vigente: true,
    ...parcial,
  };
}

export function presupuesto(parcial: Partial<Presupuesto> = {}): Presupuesto {
  secuencia += 1;
  return {
    id: secuencia,
    paciente_id: 3,
    profesional_id: 1,
    estado: "borrador",
    total: "36000.00",
    motivo_rechazo: null,
    presentado_at: null,
    decidido_at: null,
    created_at: "2026-10-30T10:00:00Z",
    updated_at: "2026-10-30T10:00:00Z",
    cargo_anulado: false,
    es_propio: true,
    items: [item()],
    ...parcial,
  };
}

export function respuestaJson(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

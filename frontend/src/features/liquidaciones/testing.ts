/** Fixtures compartidas por los tests de liquidaciones (datos 100% ficticios). */
import type {
  ItemLiquidacion,
  Liquidacion,
  LiquidacionDetalle,
  ObraSocial,
  PlanLiquidacion,
} from "./tipos";

let secuencia = 500;

export function item(parcial: Partial<ItemLiquidacion> = {}): ItemLiquidacion {
  secuencia += 1;
  return {
    id: secuencia,
    item_presupuesto_id: secuencia + 1000,
    fecha_prestacion: "2026-10-15",
    paciente_nombre: "Ficticia, Ana",
    codigo: "N-003",
    descripcion: "Obturación simple",
    cantidad: 1,
    monto: "10500.00",
    revision: false,
    ...parcial,
  };
}

export function plan(parcial: Partial<PlanLiquidacion> = {}): PlanLiquidacion {
  return {
    plan_id: 1,
    plan_nombre: "Plan Base",
    subtotal: "10500.00",
    items: [item()],
    ...parcial,
  };
}

export function liquidacion(parcial: Partial<Liquidacion> = {}): Liquidacion {
  return {
    id: 7,
    os_id: 1,
    obra_social: "OS Ficticia Demo",
    periodo: "2026-10-01",
    estado: "borrador",
    total: "10500.00",
    cantidad_items: 1,
    cantidad_revision: 0,
    creada_por: 1,
    presentada_at: null,
    cobrada_at: null,
    cobro_revertido_at: null,
    created_at: "2026-10-31T15:00:00Z",
    ...parcial,
  };
}

export function detalle(parcial: Partial<LiquidacionDetalle> = {}): LiquidacionDetalle {
  return { ...liquidacion(), planes: [plan()], revertida: false, ...parcial };
}

export function obraSocial(parcial: Partial<ObraSocial> = {}): ObraSocial {
  return { id: 1, nombre: "OS Ficticia Demo", activa: true, created_at: "2026-10-01T12:00:00Z", ...parcial };
}

export function respuestaJson(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

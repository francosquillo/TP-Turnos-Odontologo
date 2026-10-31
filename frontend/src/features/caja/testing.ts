/** Fixtures compartidas por los tests de caja (datos 100% ficticios). */
import type { Caja, Cobro, EstadoCaja, Recibo } from "./tipos";

let secuencia = 100;

export function recibo(parcial: Partial<Recibo> = {}): Recibo {
  secuencia += 1;
  return {
    id: secuencia,
    numero: secuencia - 100,
    paciente_id: 3,
    paciente_nombre: "Ana Ficticia",
    monto: "400.00",
    medio: "efectivo",
    fecha: "2026-10-31",
    emitido_por: 2,
    created_at: "2026-10-31T15:00:00Z",
    anulado: false,
    motivo_anulacion: null,
    anulado_por: null,
    anulado_at: null,
    ...parcial,
  };
}

export function cobro(parcial: Partial<Cobro> = {}): Cobro {
  return { ...recibo(), presupuesto_id: 31, presupuesto_estado: "aceptado", ...parcial };
}

export function caja(parcial: Partial<Caja> = {}): Caja {
  return {
    id: 7,
    fecha: "2026-10-31",
    estado: "abierta",
    abierta_por: 2,
    total_sistema: "1500.00",
    total_contado: null,
    diferencia: null,
    motivo_diferencia: null,
    cerrada_por: null,
    cerrada_at: null,
    ...parcial,
  };
}

export function estadoCaja(parcial: Partial<EstadoCaja> = {}): EstadoCaja {
  return {
    fecha: "2026-10-31",
    hoy: "2026-10-31",
    operable: true,
    bloqueo: null,
    caja: caja(),
    desglose: [
      { medio: "efectivo", subtotal: "1000.00" },
      { medio: "transferencia", subtotal: "500.00" },
    ],
    ...parcial,
  };
}

export function respuestaJson(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

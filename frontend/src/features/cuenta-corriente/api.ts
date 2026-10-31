/** API de cuenta corriente C-09: siempre con `fetchConAuth`, tipada y sin `any`.
 *
 * El saldo y los montos llegan como texto decimal y se conservan como texto: no hay
 * aritmetica de dinero en el cliente. El motivo de una anulacion viaja en el cuerpo,
 * nunca en la URL, y nada se escribe en consola.
 */
import { fetchConAuth } from "../../shared/api-client";
import {
  esObjeto,
  esTextoONulo,
  inesperada,
  pedir,
  type FetchAutenticado,
} from "../../shared/api-json";
import { esTipoMovimiento } from "./tipos";
import type { Cuenta, Movimiento, Pendiente } from "./tipos";

const esImporte = (valor: unknown): valor is string =>
  typeof valor === "string" && /^-?\d+(\.\d+)?$/.test(valor);

const esNumeroONulo = (valor: unknown): valor is number | null =>
  valor === null || typeof valor === "number";

function esMovimiento(valor: unknown): valor is Movimiento {
  return (
    esObjeto(valor) &&
    typeof valor["id"] === "number" &&
    esTipoMovimiento(valor["tipo"]) &&
    esImporte(valor["monto"]) &&
    typeof valor["concepto"] === "string" &&
    esTextoONulo(valor["motivo"]) &&
    esNumeroONulo(valor["turno_id"]) &&
    esNumeroONulo(valor["presupuesto_id"]) &&
    esNumeroONulo(valor["recibo_id"]) &&
    esNumeroONulo(valor["anula_a_id"]) &&
    typeof valor["creado_por"] === "number" &&
    typeof valor["created_at"] === "string" &&
    typeof valor["anulado"] === "boolean"
  );
}

function esPendiente(valor: unknown): valor is Pendiente {
  return (
    esObjeto(valor) &&
    typeof valor["presupuesto_id"] === "number" &&
    esImporte(valor["total"]) &&
    esImporte(valor["pendiente"])
  );
}

/** `pendientes` es opcional en la entrada (C-10, D-17): su ausencia equivale a una lista vacia. */
function esCuentaCruda(valor: unknown): valor is Omit<Cuenta, "pendientes"> & { pendientes?: Pendiente[] } {
  if (!esObjeto(valor)) return false;
  const movimientos = valor["movimientos"];
  const pendientes = valor["pendientes"];
  return (
    typeof valor["paciente_id"] === "number" &&
    esImporte(valor["saldo"]) &&
    Array.isArray(movimientos) &&
    movimientos.every(esMovimiento) &&
    (pendientes === undefined || (Array.isArray(pendientes) && pendientes.every(esPendiente)))
  );
}

/** Saldo y movimientos del paciente; consultar no crea nada en el servidor. */
export async function consultarCuenta(
  pacienteId: number,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Cuenta> {
  const { respuesta, datos } = await pedir(`/cuentas/${pacienteId}`, fetchFn);
  if (!esCuentaCruda(datos)) throw inesperada(respuesta, "cuenta corriente");
  return { ...datos, pendientes: datos.pendientes ?? [] };
}

/** Anula un cargo: el servidor crea un contramovimiento y devuelve esa fila. */
export async function anularMovimiento(
  pacienteId: number,
  movimientoId: number,
  motivo: string,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Movimiento> {
  const { respuesta, datos } = await pedir(
    `/cuentas/${pacienteId}/movimientos/${movimientoId}/anular`,
    fetchFn,
    "POST",
    { motivo },
  );
  if (!esMovimiento(datos)) throw inesperada(respuesta, "movimiento");
  return datos;
}

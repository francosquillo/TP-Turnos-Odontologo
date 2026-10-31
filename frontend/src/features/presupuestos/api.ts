/** API de presupuestos C-09: siempre con `fetchConAuth`, tipada y sin `any`.
 *
 * Los motivos (rechazo y baja) viajan en el cuerpo, nunca en la URL, y nada de lo
 * clinico se escribe en consola. Los importes llegan como texto decimal y se
 * conservan como texto: el cliente no hace aritmetica de dinero.
 */
import { fetchConAuth } from "../../shared/api-client";
import {
  esObjeto,
  esTextoONulo,
  inesperada,
  pedir,
  type FetchAutenticado,
} from "../../shared/api-json";
import { CARAS } from "../odontograma/tipos";
import { esEstadoPresupuesto } from "./tipos";
import type {
  EstadoPresupuesto,
  ItemEntrada,
  ItemPresupuesto,
  Presupuesto,
  Tratamiento,
} from "./tipos";

const esImporte = (valor: unknown): valor is string =>
  typeof valor === "string" && /^-?\d+(\.\d+)?$/.test(valor);

const esNumeroONulo = (valor: unknown): valor is number | null =>
  valor === null || typeof valor === "number";

function esItem(valor: unknown): valor is ItemPresupuesto {
  if (!esObjeto(valor)) return false;
  const cara = valor["cara"];
  return (
    typeof valor["id"] === "number" &&
    typeof valor["hallazgo_id"] === "number" &&
    typeof valor["tratamiento_id"] === "number" &&
    typeof valor["tratamiento_nombre"] === "string" &&
    esNumeroONulo(valor["pieza_fdi"]) &&
    (cara === null || (typeof cara === "string" && (CARAS as readonly string[]).includes(cara))) &&
    typeof valor["cantidad"] === "number" &&
    esImporte(valor["precio"]) &&
    esImporte(valor["subtotal"]) &&
    typeof valor["hallazgo_vigente"] === "boolean"
  );
}

function esPresupuesto(valor: unknown): valor is Presupuesto {
  if (!esObjeto(valor)) return false;
  const items = valor["items"];
  return (
    typeof valor["id"] === "number" &&
    typeof valor["paciente_id"] === "number" &&
    typeof valor["profesional_id"] === "number" &&
    esEstadoPresupuesto(valor["estado"]) &&
    esImporte(valor["total"]) &&
    esTextoONulo(valor["motivo_rechazo"]) &&
    esTextoONulo(valor["presentado_at"]) &&
    esTextoONulo(valor["decidido_at"]) &&
    typeof valor["created_at"] === "string" &&
    typeof valor["cargo_anulado"] === "boolean" &&
    typeof valor["es_propio"] === "boolean" &&
    Array.isArray(items) &&
    items.every(esItem)
  );
}

function esTratamiento(valor: unknown): valor is Tratamiento {
  return (
    esObjeto(valor) &&
    typeof valor["id"] === "number" &&
    typeof valor["codigo"] === "string" &&
    esTextoONulo(valor["codigo_nomenclador"]) &&
    typeof valor["nombre"] === "string" &&
    esImporte(valor["precio_base"])
  );
}

function presupuestoDe(respuesta: Response, datos: unknown): Presupuesto {
  if (!esPresupuesto(datos)) throw inesperada(respuesta, "presupuesto");
  return datos;
}

export async function listarPresupuestos(
  pacienteId: number,
  estado?: EstadoPresupuesto,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Presupuesto[]> {
  const filtro = estado === undefined ? "" : `&estado=${estado}`;
  const { respuesta, datos } = await pedir(`/presupuestos?paciente_id=${pacienteId}${filtro}`, fetchFn);
  if (!Array.isArray(datos) || !datos.every(esPresupuesto)) throw inesperada(respuesta, "presupuestos");
  return datos;
}

export async function obtenerPresupuesto(
  id: number,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Presupuesto> {
  const { respuesta, datos } = await pedir(`/presupuestos/${id}`, fetchFn);
  return presupuestoDe(respuesta, datos);
}

export async function crearPresupuesto(
  pacienteId: number,
  items: ItemEntrada[],
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Presupuesto> {
  const { respuesta, datos } = await pedir("/presupuestos", fetchFn, "POST", {
    paciente_id: pacienteId,
    items,
  });
  return presupuestoDe(respuesta, datos);
}

/** Reemplaza la lista completa de items de un borrador. */
export async function reemplazarItems(
  id: number,
  items: ItemEntrada[],
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Presupuesto> {
  const { respuesta, datos } = await pedir(`/presupuestos/${id}`, fetchFn, "PUT", { items });
  return presupuestoDe(respuesta, datos);
}

export async function presentarPresupuesto(
  id: number,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Presupuesto> {
  const { respuesta, datos } = await pedir(`/presupuestos/${id}/presentar`, fetchFn, "POST", {});
  return presupuestoDe(respuesta, datos);
}

/** Acepta y el servidor genera el cargo en la cuenta corriente. */
export async function aceptarPresupuesto(
  id: number,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Presupuesto> {
  const { respuesta, datos } = await pedir(`/presupuestos/${id}/aceptar`, fetchFn, "POST", {});
  return presupuestoDe(respuesta, datos);
}

export async function rechazarPresupuesto(
  id: number,
  motivo: string,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Presupuesto> {
  const { respuesta, datos } = await pedir(`/presupuestos/${id}/rechazar`, fetchFn, "POST", { motivo });
  return presupuestoDe(respuesta, datos);
}

export async function darDeBajaPresupuesto(
  id: number,
  motivoBaja: string,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Presupuesto> {
  const { respuesta, datos } = await pedir(`/presupuestos/${id}/baja`, fetchFn, "POST", {
    motivo_baja: motivoBaja,
  });
  return presupuestoDe(respuesta, datos);
}

/** Catalogo de tratamientos (solo lectura, C-08). */
export async function listarTratamientos(
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Tratamiento[]> {
  const { respuesta, datos } = await pedir("/tratamientos", fetchFn);
  if (!Array.isArray(datos) || !datos.every(esTratamiento)) throw inesperada(respuesta, "tratamientos");
  return datos;
}

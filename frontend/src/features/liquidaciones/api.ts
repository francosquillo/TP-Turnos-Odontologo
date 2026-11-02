/** API de liquidaciones C-11: siempre con `fetchConAuth`, tipada y sin `any`.
 *
 * Los importes llegan como texto decimal y se conservan como texto. El motivo de una
 * reversion viaja en el cuerpo, nunca en la URL. Descartar es `POST` (no hay DELETE). Los
 * informes se descargan con la sesion autenticada como `Blob`. Nada se escribe en consola.
 */
import { apiUrl, fetchConAuth } from "../../shared/api-client";
import {
  errorDe,
  esObjeto,
  esTextoONulo,
  inesperada,
  pedir,
  type FetchAutenticado,
} from "../../shared/api-json";
import type { Medio } from "../caja/tipos";
import { esEstadoLiquidacion } from "./tipos";
import type {
  DatosGenerar,
  FormatoInforme,
  ItemLiquidacion,
  Liquidacion,
  LiquidacionDetalle,
  ObraSocial,
  PlanLiquidacion,
} from "./tipos";

const esImporte = (valor: unknown): valor is string =>
  typeof valor === "string" && /^-?\d+(\.\d+)?$/.test(valor);

function esItem(valor: unknown): valor is ItemLiquidacion {
  return (
    esObjeto(valor) &&
    typeof valor["id"] === "number" &&
    typeof valor["item_presupuesto_id"] === "number" &&
    typeof valor["fecha_prestacion"] === "string" &&
    typeof valor["paciente_nombre"] === "string" &&
    typeof valor["codigo"] === "string" &&
    typeof valor["descripcion"] === "string" &&
    typeof valor["cantidad"] === "number" &&
    esImporte(valor["monto"]) &&
    typeof valor["revision"] === "boolean"
  );
}

function esPlan(valor: unknown): valor is PlanLiquidacion {
  if (!esObjeto(valor)) return false;
  const items = valor["items"];
  return (
    typeof valor["plan_id"] === "number" &&
    typeof valor["plan_nombre"] === "string" &&
    esImporte(valor["subtotal"]) &&
    Array.isArray(items) &&
    items.every(esItem)
  );
}

function esLiquidacion(valor: unknown): valor is Liquidacion {
  return (
    esObjeto(valor) &&
    typeof valor["id"] === "number" &&
    typeof valor["os_id"] === "number" &&
    typeof valor["obra_social"] === "string" &&
    typeof valor["periodo"] === "string" &&
    esEstadoLiquidacion(valor["estado"]) &&
    esImporte(valor["total"]) &&
    typeof valor["cantidad_items"] === "number" &&
    typeof valor["cantidad_revision"] === "number" &&
    typeof valor["creada_por"] === "number" &&
    esTextoONulo(valor["presentada_at"]) &&
    esTextoONulo(valor["cobrada_at"]) &&
    esTextoONulo(valor["cobro_revertido_at"]) &&
    typeof valor["created_at"] === "string"
  );
}

function esDetalle(valor: unknown): valor is LiquidacionDetalle {
  if (!esLiquidacion(valor) || !esObjeto(valor)) return false;
  const planes = valor["planes"];
  return typeof valor["revertida"] === "boolean" && Array.isArray(planes) && planes.every(esPlan);
}

function esObraSocial(valor: unknown): valor is ObraSocial {
  return (
    esObjeto(valor) &&
    typeof valor["id"] === "number" &&
    typeof valor["nombre"] === "string" &&
    typeof valor["activa"] === "boolean" &&
    typeof valor["created_at"] === "string"
  );
}

async function detalleDe(
  ruta: string,
  fetchFn: FetchAutenticado,
  metodo: "GET" | "POST" = "GET",
  cuerpo?: unknown,
): Promise<LiquidacionDetalle> {
  const { respuesta, datos } = await pedir(ruta, fetchFn, metodo, cuerpo);
  if (!esDetalle(datos)) throw inesperada(respuesta, "liquidación");
  return datos;
}

export async function listarLiquidaciones(
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Liquidacion[]> {
  const { respuesta, datos } = await pedir("/liquidaciones", fetchFn);
  if (!Array.isArray(datos) || !datos.every(esLiquidacion)) throw inesperada(respuesta, "liquidaciones");
  return datos;
}

export function obtenerLiquidacion(
  id: number,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<LiquidacionDetalle> {
  return detalleDe(`/liquidaciones/${id}`, fetchFn);
}

/** Genera un borrador con las prestaciones del periodo; sin prestaciones el servidor responde 409. */
export function generarLiquidacion(
  datos: DatosGenerar,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<LiquidacionDetalle> {
  return detalleDe("/liquidaciones", fetchFn, "POST", datos);
}

export function presentarLiquidacion(
  id: number,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<LiquidacionDetalle> {
  return detalleDe(`/liquidaciones/${id}/presentar`, fetchFn, "POST", {});
}

/** Borra un borrador (`204`); es POST porque el cliente no tiene DELETE. */
export async function descartarLiquidacion(
  id: number,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<void> {
  await pedir(`/liquidaciones/${id}/descartar`, fetchFn, "POST", {});
}

/** Cobra la liquidacion por el total: el monto y la caja los decide el servidor. */
export function cobrarLiquidacion(
  id: number,
  medio: Medio,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<LiquidacionDetalle> {
  return detalleDe(`/liquidaciones/${id}/cobrar`, fetchFn, "POST", { medio });
}

export function revertirCobroLiquidacion(
  id: number,
  motivo: string,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<LiquidacionDetalle> {
  return detalleDe(`/liquidaciones/${id}/revertir-cobro`, fetchFn, "POST", { motivo });
}

export async function listarObrasSociales(
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<ObraSocial[]> {
  const { respuesta, datos } = await pedir("/obras-sociales", fetchFn);
  if (!Array.isArray(datos) || !datos.every(esObraSocial)) throw inesperada(respuesta, "obras sociales");
  return datos;
}

export interface Informe {
  blob: Blob;
  nombre: string;
}

/** Descarga el informe (CSV o PDF) con la sesion autenticada; el navegador no manda el Bearer
 * en un enlace comun, por eso se pide con `fetchConAuth` y se entrega como `Blob`. */
export async function descargarInforme(
  id: number,
  formato: FormatoInforme,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Informe> {
  const respuesta = await fetchFn(apiUrl(`/liquidaciones/${id}/export.${formato}`));
  if (!respuesta.ok) throw await errorDe(respuesta);
  return { blob: await respuesta.blob(), nombre: `liquidacion-${id}.${formato}` };
}

/** API de caja y recibos C-10: siempre con `fetchConAuth`, tipada y sin `any`.
 *
 * Los importes llegan como texto decimal y se conservan como texto. Los motivos viajan en el
 * cuerpo, nunca en la URL. La clave de idempotencia del cobro va en el cuerpo y no se
 * devuelve en ninguna respuesta. Nada se escribe en consola.
 */
import { fetchConAuth } from "../../shared/api-client";
import {
  esObjeto,
  esTextoONulo,
  inesperada,
  pedir,
  type FetchAutenticado,
} from "../../shared/api-json";
import { esMedio } from "./tipos";
import type {
  Bloqueo,
  Caja,
  Cobro,
  DatosCierre,
  DatosCobro,
  DesgloseMedio,
  EstadoCaja,
  Recibo,
} from "./tipos";

const esImporte = (valor: unknown): valor is string =>
  typeof valor === "string" && /^-?\d+(\.\d+)?$/.test(valor);

const esImporteONulo = (valor: unknown): valor is string | null => valor === null || esImporte(valor);

const esNumeroONulo = (valor: unknown): valor is number | null =>
  valor === null || typeof valor === "number";

const esBloqueo = (valor: unknown): valor is Bloqueo =>
  valor === "caja_pendiente" || valor === "caja_cerrada";

function esCaja(valor: unknown): valor is Caja {
  return (
    esObjeto(valor) &&
    typeof valor["id"] === "number" &&
    typeof valor["fecha"] === "string" &&
    (valor["estado"] === "abierta" || valor["estado"] === "cerrada") &&
    typeof valor["abierta_por"] === "number" &&
    esImporte(valor["total_sistema"]) &&
    esImporteONulo(valor["total_contado"]) &&
    esImporteONulo(valor["diferencia"]) &&
    esTextoONulo(valor["motivo_diferencia"]) &&
    esNumeroONulo(valor["cerrada_por"]) &&
    esTextoONulo(valor["cerrada_at"])
  );
}

function esDesglose(valor: unknown): valor is DesgloseMedio {
  return esObjeto(valor) && esMedio(valor["medio"]) && esImporte(valor["subtotal"]);
}

function esEstadoCaja(valor: unknown): valor is EstadoCaja {
  if (!esObjeto(valor)) return false;
  const desglose = valor["desglose"];
  return (
    typeof valor["fecha"] === "string" &&
    typeof valor["hoy"] === "string" &&
    typeof valor["operable"] === "boolean" &&
    (valor["bloqueo"] === null || esBloqueo(valor["bloqueo"])) &&
    (valor["caja"] === null || esCaja(valor["caja"])) &&
    Array.isArray(desglose) &&
    desglose.every(esDesglose)
  );
}

function esRecibo(valor: unknown): valor is Recibo {
  return (
    esObjeto(valor) &&
    typeof valor["id"] === "number" &&
    typeof valor["numero"] === "number" &&
    typeof valor["paciente_id"] === "number" &&
    typeof valor["paciente_nombre"] === "string" &&
    esImporte(valor["monto"]) &&
    esMedio(valor["medio"]) &&
    typeof valor["fecha"] === "string" &&
    typeof valor["emitido_por"] === "number" &&
    typeof valor["created_at"] === "string" &&
    typeof valor["anulado"] === "boolean" &&
    esTextoONulo(valor["motivo_anulacion"]) &&
    esNumeroONulo(valor["anulado_por"]) &&
    esTextoONulo(valor["anulado_at"])
  );
}

function esCobro(valor: unknown): valor is Cobro {
  return (
    esRecibo(valor) &&
    esObjeto(valor) &&
    typeof valor["presupuesto_id"] === "number" &&
    typeof valor["presupuesto_estado"] === "string"
  );
}

/** Estado de la caja de `fecha` (o la pendiente / la de hoy); consultar no crea nada. */
export async function consultarCaja(
  fecha?: string,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<EstadoCaja> {
  const ruta = fecha === undefined ? "/caja" : `/caja?fecha=${encodeURIComponent(fecha)}`;
  const { respuesta, datos } = await pedir(ruta, fetchFn);
  if (!esEstadoCaja(datos)) throw inesperada(respuesta, "caja");
  return datos;
}

/** Recibos emitidos en la caja de `fecha`, del numero mayor al menor. */
export async function listarRecibos(
  fecha: string,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Recibo[]> {
  const { respuesta, datos } = await pedir(`/recibos?fecha=${encodeURIComponent(fecha)}`, fetchFn);
  if (!Array.isArray(datos) || !datos.every(esRecibo)) throw inesperada(respuesta, "recibos");
  return datos;
}

export interface ResultadoCobro {
  cobro: Cobro;
  /** `true` si el servidor creo el recibo (201); `false` si devolvio el original (200). */
  creado: boolean;
}

/** Cobra un presupuesto. `201` = recibo nuevo, `200` = reintento con la misma clave. */
export async function cobrar(
  datos: DatosCobro,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<ResultadoCobro> {
  const { respuesta, datos: cuerpo } = await pedir("/caja/cobrar", fetchFn, "POST", datos);
  if (!esCobro(cuerpo)) throw inesperada(respuesta, "cobro");
  return { cobro: cuerpo, creado: respuesta.status === 201 };
}

/** Cierra la caja: el servidor calcula el total y la diferencia. */
export async function cerrarCaja(
  datos: DatosCierre,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Caja> {
  const { respuesta, datos: cuerpo } = await pedir("/caja/cierre", fetchFn, "POST", datos);
  if (!esCaja(cuerpo)) throw inesperada(respuesta, "cierre de caja");
  return cuerpo;
}

/** Anula un recibo (contramovimiento en la caja de hoy); devuelve el recibo anulado. */
export async function anularRecibo(
  reciboId: number,
  motivo: string,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Recibo> {
  const { respuesta, datos } = await pedir(`/recibos/${reciboId}/anular`, fetchFn, "POST", { motivo });
  if (!esRecibo(datos)) throw inesperada(respuesta, "recibo");
  return datos;
}

/** API de cobertura de obra social C-11: siempre con `fetchConAuth`, tipada y sin `any`.
 *
 * Los importes del validador llegan como texto y se conservan como texto. Nada se escribe en
 * consola.
 */
import { fetchConAuth } from "../../shared/api-client";
import {
  esObjeto,
  esTextoONulo,
  inesperada,
  pedir,
  type FetchAutenticado,
} from "../../shared/api-json";
import { esEstadoCobertura } from "./cobertura-tipos";
import type { PlanDelCatalogo, PlanPaciente, ValidadorCobertura } from "./cobertura-tipos";

const esImporte = (valor: unknown): valor is string =>
  typeof valor === "string" && /^-?\d+(\.\d+)?$/.test(valor);

const esNumeroONulo = (valor: unknown): valor is number | null =>
  valor === null || typeof valor === "number";

function esPlanPaciente(valor: unknown): valor is PlanPaciente {
  return (
    esObjeto(valor) &&
    typeof valor["paciente_id"] === "number" &&
    esNumeroONulo(valor["plan_id"]) &&
    esTextoONulo(valor["plan_nombre"]) &&
    esNumeroONulo(valor["obra_social_id"]) &&
    esTextoONulo(valor["obra_social_nombre"])
  );
}

function esPlanDelCatalogo(valor: unknown): valor is PlanDelCatalogo {
  return (
    esObjeto(valor) &&
    typeof valor["id"] === "number" &&
    typeof valor["obra_social_id"] === "number" &&
    typeof valor["obra_social_nombre"] === "string" &&
    typeof valor["nombre"] === "string" &&
    typeof valor["activo"] === "boolean" &&
    typeof valor["created_at"] === "string"
  );
}

function esValidador(valor: unknown): valor is ValidadorCobertura {
  return (
    esObjeto(valor) &&
    esEstadoCobertura(valor["estado"]) &&
    typeof valor["paciente_id"] === "number" &&
    typeof valor["tratamiento_id"] === "number" &&
    esNumeroONulo(valor["plan_id"]) &&
    esImporte(valor["precio"]) &&
    (valor["arancel"] === null || esImporte(valor["arancel"])) &&
    esImporte(valor["cubierto"]) &&
    esImporte(valor["a_cargo"]) &&
    esImporte(valor["porcentaje"]) &&
    typeof valor["fecha"] === "string"
  );
}

/** Plan actual del paciente (`secretaria` y `admin`). */
export async function obtenerPlanPaciente(
  pacienteId: number,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<PlanPaciente> {
  const { respuesta, datos } = await pedir(`/pacientes/${pacienteId}/plan`, fetchFn);
  if (!esPlanPaciente(datos)) throw inesperada(respuesta, "plan del paciente");
  return datos;
}

/** Asigna un plan o lo quita (`null`); un plan inactivo o inexistente es 409. */
export async function asignarPlanPaciente(
  pacienteId: number,
  planId: number | null,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<PlanPaciente> {
  const { respuesta, datos } = await pedir(`/pacientes/${pacienteId}/plan`, fetchFn, "PUT", {
    plan_id: planId,
  });
  if (!esPlanPaciente(datos)) throw inesperada(respuesta, "plan del paciente");
  return datos;
}

export async function listarPlanes(
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<PlanDelCatalogo[]> {
  const { respuesta, datos } = await pedir("/planes", fetchFn);
  if (!Array.isArray(datos) || !datos.every(esPlanDelCatalogo)) throw inesperada(respuesta, "planes");
  return datos;
}

/** Cobertura de un tratamiento para el plan actual del paciente, con el arancel de hoy. */
export async function validarCobertura(
  pacienteId: number,
  tratamientoId: number,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<ValidadorCobertura> {
  const { respuesta, datos } = await pedir(
    `/validador-cobertura?paciente_id=${pacienteId}&tratamiento_id=${tratamientoId}`,
    fetchFn,
  );
  if (!esValidador(datos)) throw inesperada(respuesta, "cobertura");
  return datos;
}

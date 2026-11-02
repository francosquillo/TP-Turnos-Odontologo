/** Cliente publico de GET /seguridad (C-12): sin Bearer, tipado y validado, sin `any`. */
import { apiUrl } from "../shared/api-client";
import { esObjeto } from "../shared/api-json";

export interface HechosSeguridad {
  datos_ficticios: true;
  declaracion: string;
  hash_contrasenas: string;
  access_token_min: number;
  refresh_rotativo: boolean;
  whatsapp_modo: "mock" | "real";
  whatsapp_sin_datos_clinicos: boolean;
  google_calendar_habilitado: boolean;
  google_calendar_nota: string;
  auditoria: string[];
  respaldos: string[];
  cifrado: string;
}

const esLista = (valor: unknown): valor is string[] =>
  Array.isArray(valor) && valor.every((x) => typeof x === "string");

function esHechos(valor: unknown): valor is HechosSeguridad {
  return (
    esObjeto(valor) &&
    valor["datos_ficticios"] === true &&
    typeof valor["declaracion"] === "string" &&
    typeof valor["hash_contrasenas"] === "string" &&
    typeof valor["access_token_min"] === "number" &&
    typeof valor["refresh_rotativo"] === "boolean" &&
    (valor["whatsapp_modo"] === "mock" || valor["whatsapp_modo"] === "real") &&
    typeof valor["whatsapp_sin_datos_clinicos"] === "boolean" &&
    typeof valor["google_calendar_habilitado"] === "boolean" &&
    typeof valor["google_calendar_nota"] === "string" &&
    esLista(valor["auditoria"]) &&
    esLista(valor["respaldos"]) &&
    typeof valor["cifrado"] === "string"
  );
}

/** Devuelve los hechos o `null` si el backend no responde o la forma no es la esperada. */
export async function obtenerSeguridad(): Promise<HechosSeguridad | null> {
  try {
    const respuesta = await fetch(apiUrl("/seguridad"));
    if (!respuesta.ok) return null;
    const cuerpo = (await respuesta.json()) as unknown;
    return esHechos(cuerpo) ? cuerpo : null;
  } catch {
    return null;
  }
}

/** Tipos y reglas puras del odontograma FDI (C-08, D-02/D-03/D-13). */

export type Cara =
  | "oclusal"
  | "mesial"
  | "distal"
  | "vestibular"
  | "palatina"
  | "lingual"
  | "raiz"
  | "pieza_completa";

export type Alcance = "cualquiera" | "pieza";

export const CARAS: readonly Cara[] = [
  "oclusal",
  "mesial",
  "distal",
  "vestibular",
  "palatina",
  "lingual",
  "raiz",
  "pieza_completa",
];

export interface EstadoCatalogo {
  codigo: string;
  nombre: string;
  alcance: Alcance;
}

export interface Catalogo {
  version: number;
  estados: EstadoCatalogo[];
}

export interface Historia {
  id: number;
  paciente_id: number;
  antecedentes: string | null;
  alergias: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  motivo_baja: string | null;
}

export interface Hallazgo {
  id: number;
  hc_id: number;
  pieza_fdi: number;
  cara: Cara;
  estado: string;
  catalogo_version: number;
  fecha: string;
  profesional_id: number;
  corrige_a_id: number | null;
  deleted_at: string | null;
  motivo_baja: string | null;
  /** El servidor marca si quien consulta es el autor (solo el autor corrige o anula). */
  es_propio: boolean;
}

export interface DatosHallazgo {
  pieza_fdi: number;
  cara: Cara;
  estado: string;
}

export interface Listado {
  alergias: string | null;
  hallazgos: Hallazgo[];
}

export interface Cuadrante {
  id: "sup-der" | "sup-izq" | "inf-der" | "inf-izq";
  nombre: string;
  piezas: readonly number[];
}

const descendente = (decena: number): number[] =>
  [8, 7, 6, 5, 4, 3, 2, 1].map((n) => decena * 10 + n);
const ascendente = (decena: number): number[] =>
  [1, 2, 3, 4, 5, 6, 7, 8].map((n) => decena * 10 + n);

/** Orden clinico: superior 18→11 | 21→28, inferior 48→41 | 31→38. */
export const CUADRANTES: readonly Cuadrante[] = [
  { id: "sup-der", nombre: "Superior derecho", piezas: descendente(1) },
  { id: "sup-izq", nombre: "Superior izquierdo", piezas: ascendente(2) },
  { id: "inf-der", nombre: "Inferior derecho", piezas: descendente(4) },
  { id: "inf-izq", nombre: "Inferior izquierdo", piezas: ascendente(3) },
];

export function todasLasPiezas(): number[] {
  return CUADRANTES.flatMap((c) => [...c.piezas]);
}

const esSuperior = (pieza: number): boolean => pieza < 30;

/** Caras que ofrece el formulario: sin palatina abajo ni lingual arriba (D-03). */
export function carasPermitidas(pieza: number, alcance: Alcance): Cara[] {
  if (alcance === "pieza") return ["pieza_completa"];
  return CARAS.filter((cara) =>
    cara === "palatina" ? esSuperior(pieza) : cara === "lingual" ? !esSuperior(pieza) : true,
  );
}

const ROTULOS: Record<Cara, string> = {
  oclusal: "Oclusal",
  mesial: "Mesial",
  distal: "Distal",
  vestibular: "Vestibular",
  palatina: "Palatina",
  lingual: "Lingual",
  raiz: "Raíz",
  pieza_completa: "Pieza completa",
};

/** En incisivos y caninos (x1-x3) `oclusal` es el borde incisal. */
export function etiquetaCara(pieza: number, cara: Cara): string {
  if (cara === "oclusal" && pieza % 10 <= 3) return "Incisal";
  return ROTULOS[cara];
}

const masReciente = (a: Hallazgo, b: Hallazgo): number => {
  const porFecha = Date.parse(b.fecha) - Date.parse(a.fecha);
  return porFecha !== 0 ? porFecha : b.id - a.id;
};

/**
 * Estado vigente por cara a partir de los hallazgos de UNA pieza: el mas
 * reciente activo de cada cara; una `pieza_completa` mas reciente tapa las caras
 * anteriores, y una cara mas reciente prevalece sobre una `pieza_completa` vieja.
 */
export function estadoVigente(hallazgos: readonly Hallazgo[]): Map<Cara, Hallazgo> {
  const activos = hallazgos.filter((h) => h.deleted_at === null).sort(masReciente);
  const porCara = new Map<Cara, Hallazgo>();
  for (const h of activos) {
    if (!porCara.has(h.cara)) porCara.set(h.cara, h);
  }
  const completa = porCara.get("pieza_completa");
  if (completa !== undefined) {
    for (const [cara, h] of porCara) {
      if (cara !== "pieza_completa" && masReciente(completa, h) < 0) porCara.delete(cara);
    }
  }
  return porCara;
}

/** Historial de una pieza: del hallazgo mas reciente al mas antiguo (anulados incluidos). */
export function ordenarHistorial(hallazgos: readonly Hallazgo[]): Hallazgo[] {
  return [...hallazgos].sort(masReciente);
}

/** Alcance del estado en el catalogo (`cualquiera` si el codigo no figura). */
export function alcanceDe(catalogo: Catalogo, estado: string): Alcance {
  return catalogo.estados.find((e) => e.codigo === estado)?.alcance ?? "cualquiera";
}

const FORMATO_FECHA = new Intl.DateTimeFormat("es-AR", {
  dateStyle: "short",
  timeStyle: "short",
  timeZone: "America/Argentina/Buenos_Aires",
});

export function formatoFecha(iso: string): string {
  return FORMATO_FECHA.format(new Date(iso));
}

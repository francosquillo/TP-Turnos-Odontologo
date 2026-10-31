/** Formato de importes (C-09, D-21): sin aritmetica de dinero en el cliente.
 *
 * La API entrega los importes como texto decimal ("2501.00"). Aca solo se
 * presenta ese texto con el formato es-AR; el total y el saldo siempre los da
 * el servidor. Nunca se convierte a `number`: el entero se agrupa con `BigInt`
 * y `Intl.NumberFormat("es-AR")`, y los decimales se toman del texto.
 */

const PATRON = /^(-?)(\d+)(?:\.(\d+))?$/;
const SIN_IMPORTE = "—";
const ENTEROS = new Intl.NumberFormat("es-AR", { useGrouping: true });

export type EstadoSaldo = "debe" | "sin-deuda" | "a-favor";

function descomponer(valor: string): { negativo: boolean; entero: string; decimales: string } | null {
  const partes = PATRON.exec(valor);
  if (partes === null) return null;
  const decimales = (partes[3] ?? "").padEnd(2, "0").slice(0, 2);
  return { negativo: partes[1] === "-", entero: partes[2] ?? "0", decimales };
}

/** "2501.00" -> "$ 2.501,00"; negativos como "-$ 500,00"; forma inesperada -> "—". */
export function formatearMoneda(valor: string): string {
  const partes = descomponer(valor);
  if (partes === null) return SIN_IMPORTE;
  const entero = ENTEROS.format(BigInt(partes.entero));
  return `${partes.negativo ? "-" : ""}$ ${entero},${partes.decimales}`;
}

/** Clasifica un saldo decimal (positivo = deuda del paciente) sin convertirlo a numero. */
export function estadoDeSaldo(valor: string): EstadoSaldo {
  const partes = descomponer(valor);
  if (partes === null) return "sin-deuda";
  const esCero = !/[1-9]/.test(partes.entero + partes.decimales);
  if (esCero) return "sin-deuda";
  return partes.negativo ? "a-favor" : "debe";
}

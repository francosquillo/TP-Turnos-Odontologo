/** Formateo de fechas fijo en America/Argentina/Buenos_Aires (no depende de la TZ de la maquina). */
const ZONA = "America/Argentina/Buenos_Aires";

const FORMATO_HORA = new Intl.DateTimeFormat("en-GB", {
  timeZone: ZONA,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const FORMATO_DIA = new Intl.DateTimeFormat("en-CA", {
  timeZone: ZONA,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** "HH:MM" en hora argentina. */
export function horaAR(iso: string): string {
  return FORMATO_HORA.format(new Date(iso));
}

/** "YYYY-MM-DD" del dia argentino. */
export function claveDiaAR(iso: string): string {
  return FORMATO_DIA.format(new Date(iso));
}

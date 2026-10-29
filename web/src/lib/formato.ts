/* Formatos para México. Las horas de la API vienen en UTC; se muestran en hora del centro. */

const ZONA = "America/Mexico_City";

const numero = new Intl.NumberFormat("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const conSigno = new Intl.NumberFormat("es-MX", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: "exceptZero",
});

export const formatoNumero = (v: number) => numero.format(v);
export const formatoVariacion = (v: number) => conSigno.format(v);

/** "2026-10-29" (fecha sin hora) → "29 oct 2026", sin corrimiento de zona. */
export function formatoFecha(iso: string, opciones: Intl.DateTimeFormatOptions = {}): string {
  const [a, m, d] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("es-MX", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
    ...opciones,
  }).format(new Date(Date.UTC(a, m - 1, d)));
}

/** "2026-10-29T13:45:00" (UTC sin zona) → Date. */
export const desdeUtc = (iso: string) => new Date(iso.endsWith("Z") ? iso : `${iso}Z`);

export function formatoFechaHora(fecha: Date): string {
  return new Intl.DateTimeFormat("es-MX", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: ZONA,
  }).format(fecha);
}

/** "hoy, 07:45" o "28 oct, 07:45". */
export function formatoMomento(fecha: Date): string {
  if (!esHoyEnMexico(fecha)) return formatoFechaHora(fecha);
  const hora = new Intl.DateTimeFormat("es-MX", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: ZONA,
  }).format(fecha);
  return `hoy, ${hora}`;
}

export function esHoyEnMexico(fecha: Date): boolean {
  const f = new Intl.DateTimeFormat("en-CA", { timeZone: ZONA });
  return f.format(fecha) === f.format(new Date());
}

export function hoyEnMexico(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: ZONA }).format(new Date());
}

export function restarDias(isoFecha: string, dias: number): string {
  const [a, m, d] = isoFecha.split("-").map(Number);
  return new Date(Date.UTC(a, m - 1, d - dias)).toISOString().slice(0, 10);
}

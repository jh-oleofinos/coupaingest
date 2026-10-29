import { create } from "zustand";

/* Estado de interfaz del tablero (no datos: los datos los maneja TanStack Query). */

export const RANGOS = [
  { clave: "1M", dias: 31, etiqueta: "último mes" },
  { clave: "3M", dias: 92, etiqueta: "últimos 3 meses" },
  { clave: "6M", dias: 183, etiqueta: "últimos 6 meses" },
  { clave: "1A", dias: 366, etiqueta: "último año" },
  { clave: "2A", dias: 731, etiqueta: "últimos 2 años" },
] as const;

export type ClaveRango = (typeof RANGOS)[number]["clave"];

type Estado = {
  seleccionado: string | null;
  rango: ClaveRango;
  seleccionar: (codigo: string) => void;
  cambiarRango: (rango: ClaveRango) => void;
};

export const useTableroCommodities = create<Estado>((set) => ({
  seleccionado: null,
  rango: "3M",
  seleccionar: (codigo) => set({ seleccionado: codigo }),
  cambiarRango: (rango) => set({ rango }),
}));

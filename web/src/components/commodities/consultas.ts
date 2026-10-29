"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { obtenerJson } from "@/components/proveedores";
import { hoyEnMexico, restarDias } from "@/lib/formato";
import type { EstadoCarga, ResumenCommodity, Serie } from "@/lib/tipos";
import { RANGOS, type ClaveRango } from "@/store/tablero-commodities";

// El job carga una vez al día; se revisa cada 10 minutos para mostrar lo nuevo sin recargar.
const REFRESCO_MS = 10 * 60 * 1000;

export function useResumen() {
  return useQuery({
    queryKey: ["commodities", "resumen"],
    queryFn: () => obtenerJson<ResumenCommodity[]>("/api/commodities/resumen"),
    refetchInterval: REFRESCO_MS,
  });
}

export function useEstadoCarga() {
  return useQuery({
    queryKey: ["commodities", "estado-carga"],
    queryFn: () => obtenerJson<EstadoCarga>("/api/commodities/estado-carga"),
    refetchInterval: REFRESCO_MS,
  });
}

export function useSerie(codigo: string | null, rango: ClaveRango) {
  const dias = RANGOS.find((r) => r.clave === rango)!.dias;
  const desde = restarDias(hoyEnMexico(), dias);
  return useQuery({
    queryKey: ["commodities", "serie", codigo, rango],
    queryFn: () =>
      obtenerJson<Serie>(`/api/commodities/${encodeURIComponent(codigo!)}/serie?desde=${desde}`),
    enabled: Boolean(codigo),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESCO_MS,
  });
}

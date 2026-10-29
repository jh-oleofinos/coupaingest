"use client";

import { Minus, TrendingDown, TrendingUp } from "lucide-react";

import { formatoFecha, formatoNumero, formatoVariacion } from "@/lib/formato";
import type { ResumenCommodity } from "@/lib/tipos";
import { cn } from "@/lib/utils";

export function TarjetaCommodity({
  dato,
  seleccionado,
  onSeleccionar,
}: {
  dato: ResumenCommodity;
  seleccionado: boolean;
  onSeleccionar: () => void;
}) {
  const variacion = dato.variacion_pct !== null ? Number(dato.variacion_pct) : null;
  const Icono = variacion === null || variacion === 0 ? Minus : variacion > 0 ? TrendingUp : TrendingDown;
  const color =
    variacion === null || variacion === 0
      ? "text-muted-foreground"
      : variacion > 0
        ? "text-positivo"
        : "text-negativo";

  return (
    <button
      type="button"
      onClick={onSeleccionar}
      aria-pressed={seleccionado}
      className={cn(
        "group flex min-w-0 flex-col gap-2 rounded-xl border bg-card p-3 text-left md:gap-3 md:p-4 shadow-sm transition-colors outline-none",
        "hover:border-primary/40 focus-visible:ring-[3px] focus-visible:ring-ring/50",
        seleccionado && "border-primary ring-1 ring-primary",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm leading-snug font-medium text-muted-foreground">{dato.nombre}</span>
        <span className="text-xs text-muted-foreground">{dato.unidad}</span>
      </div>
      {dato.ultimo ? (
        <>
          <span className="tabular text-xl font-semibold tracking-tight md:text-2xl">
            {formatoNumero(Number(dato.ultimo.valor))}
          </span>
          <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1 text-xs">
            <span className={cn("tabular inline-flex items-center gap-1 font-medium", color)}>
              <Icono className="size-3.5" aria-hidden />
              {variacion === null ? "Sin día previo" : `${formatoVariacion(variacion)} %`}
              {variacion !== null && <span className="sr-only"> contra el día anterior</span>}
            </span>
            <span className="text-muted-foreground">{formatoFecha(dato.ultimo.fecha)}</span>
          </div>
        </>
      ) : (
        <span className="text-sm text-muted-foreground">Sin datos</span>
      )}
    </button>
  );
}

"use client";

/* Contenedor de gráficas al estilo de shadcn/ui (Recharts + tokens de color). */

import * as React from "react";
import * as RechartsPrimitive from "recharts";

import { cn } from "@/lib/utils";

export type ChartConfig = Record<string, { label?: React.ReactNode; color?: string }>;

const ChartContext = React.createContext<{ config: ChartConfig } | null>(null);

function useChart() {
  const ctx = React.useContext(ChartContext);
  if (!ctx) throw new Error("useChart debe usarse dentro de ChartContainer.");
  return ctx;
}

function ChartContainer({
  config,
  className,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  config: ChartConfig;
  children: React.ComponentProps<typeof RechartsPrimitive.ResponsiveContainer>["children"];
}) {
  const estilo = Object.fromEntries(
    Object.entries(config)
      .filter(([, v]) => v.color)
      .map(([k, v]) => [`--color-${k}`, v.color]),
  ) as React.CSSProperties;

  return (
    <ChartContext.Provider value={{ config }}>
      <div
        data-slot="chart"
        style={estilo}
        className={cn(
          "flex aspect-video justify-center text-xs [&_.recharts-cartesian-axis-tick_text]:fill-muted-foreground [&_.recharts-cartesian-grid_line[stroke='#ccc']]:stroke-border/60 [&_.recharts-curve.recharts-tooltip-cursor]:stroke-border [&_.recharts-surface]:outline-hidden",
          className,
        )}
        {...props}
      >
        <RechartsPrimitive.ResponsiveContainer>{children}</RechartsPrimitive.ResponsiveContainer>
      </div>
    </ChartContext.Provider>
  );
}

const ChartTooltip = RechartsPrimitive.Tooltip;

type ItemTooltip = { dataKey?: string | number; value?: unknown; color?: string };

function ChartTooltipContent({
  active,
  payload,
  label,
  formatearValor,
  formatearEtiqueta,
}: {
  active?: boolean;
  payload?: ItemTooltip[];
  label?: unknown;
  formatearValor?: (valor: number) => string;
  formatearEtiqueta?: (etiqueta: unknown) => string;
}) {
  const { config } = useChart();
  if (!active || !payload?.length) return null;
  return (
    <div className="grid min-w-32 gap-1.5 rounded-lg border bg-card px-2.5 py-1.5 text-xs shadow-xl">
      <div className="font-medium">{formatearEtiqueta ? formatearEtiqueta(label) : String(label)}</div>
      {payload.map((item) => {
        const clave = String(item.dataKey ?? "");
        return (
          <div key={clave} className="flex items-center gap-2">
            <span
              aria-hidden
              className="size-2.5 shrink-0 rounded-[2px]"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-muted-foreground">{config[clave]?.label ?? clave}</span>
            <span className="tabular ml-auto font-mono font-medium text-foreground">
              {formatearValor ? formatearValor(Number(item.value)) : String(item.value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export { ChartContainer, ChartTooltip, ChartTooltipContent };

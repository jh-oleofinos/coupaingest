"use client";

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { formatoFecha, formatoNumero } from "@/lib/formato";
import type { Serie } from "@/lib/tipos";

const formatoEje = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 0 });

export function GraficaSerie({ serie }: { serie: Serie }) {
  const config: ChartConfig = { valor: { label: serie.unidad, color: "var(--chart-1)" } };
  const datos = serie.puntos.map((p) => ({ fecha: p.fecha, valor: Number(p.valor) }));
  const valores = datos.map((d) => d.valor);
  const min = Math.min(...valores);
  const max = Math.max(...valores);

  return (
    <figure>
      <ChartContainer config={config} className="aspect-auto h-72 w-full">
        <LineChart data={datos} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="fecha"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            minTickGap={40}
            tickFormatter={(f: string) => formatoFecha(f, { year: undefined })}
          />
          <YAxis
            domain={["auto", "auto"]}
            tickLine={false}
            axisLine={false}
            width={56}
            tickFormatter={(v: number) => formatoEje.format(v)}
          />
          <ChartTooltip
            cursor
            content={
              <ChartTooltipContent
                formatearValor={formatoNumero}
                formatearEtiqueta={(f) => formatoFecha(String(f))}
              />
            }
          />
          <Line
            dataKey="valor"
            type="linear"
            stroke="var(--color-valor)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ChartContainer>
      <figcaption className="sr-only">
        Evolución de {serie.nombre} en {serie.unidad}: de {formatoNumero(datos[0]?.valor ?? 0)} el{" "}
        {datos[0] ? formatoFecha(datos[0].fecha) : ""} a {formatoNumero(datos.at(-1)?.valor ?? 0)} el{" "}
        {datos.at(-1) ? formatoFecha(datos.at(-1)!.fecha) : ""}. Mínimo {formatoNumero(min)}, máximo{" "}
        {formatoNumero(max)}. El detalle está en la tabla de histórico.
      </figcaption>
    </figure>
  );
}

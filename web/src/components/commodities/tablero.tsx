"use client";

import { CircleAlert, RefreshCw } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { RANGOS, useTableroCommodities, type ClaveRango } from "@/store/tablero-commodities";

import { useResumen, useSerie } from "./consultas";
import { GraficaSerie } from "./grafica-serie";
import { TablaPrecios } from "./tabla-precios";
import { TarjetaCommodity } from "./tarjeta-commodity";

function ErrorCarga({ onReintentar }: { onReintentar: () => void }) {
  return (
    <Alert variant="destructive">
      <CircleAlert aria-hidden />
      <AlertTitle>No se pudieron cargar los datos</AlertTitle>
      <AlertDescription>
        <p>Revisa tu conexión e inténtalo de nuevo. Si el problema sigue, avisa al administrador.</p>
        <Button variant="outline" size="sm" className="mt-2" onClick={onReintentar}>
          <RefreshCw aria-hidden /> Reintentar
        </Button>
      </AlertDescription>
    </Alert>
  );
}

export function TableroCommodities() {
  const resumen = useResumen();
  const { seleccionado, rango, seleccionar, cambiarRango } = useTableroCommodities();

  const lista = resumen.data ?? [];
  const actual = lista.find((c) => c.codigo === seleccionado) ?? lista[0] ?? null;
  const serie = useSerie(actual?.codigo ?? null, rango);
  const etiquetaRango = RANGOS.find((r) => r.clave === rango)!.etiqueta;

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 md:p-6">
      <section aria-labelledby="titulo-resumen" className="grid gap-3">
        <h2 id="titulo-resumen" className="sr-only">
          Último precio por commodity
        </h2>
        {resumen.isPending ? (
          <div className="grid grid-cols-2 gap-3 md:gap-4 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-xl md:h-32" />
            ))}
          </div>
        ) : resumen.isError ? (
          <ErrorCarga onReintentar={() => resumen.refetch()} />
        ) : lista.length === 0 ? (
          <Card>
            <CardContent className="text-sm text-muted-foreground">
              Aún no hay commodities cargados. Aparecerán aquí después de la primera carga diaria.
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-2 gap-3 md:gap-4 xl:grid-cols-4">
            {lista.map((c) => (
              <TarjetaCommodity
                key={c.codigo}
                dato={c}
                seleccionado={c.codigo === actual?.codigo}
                onSeleccionar={() => seleccionar(c.codigo)}
              />
            ))}
          </div>
        )}
      </section>

      {actual && (
        <>
          <Card>
            <CardHeader className="flex flex-wrap items-start justify-between gap-3">
              <div className="grid gap-1.5">
                <CardTitle>
                  <h2>{actual.nombre}</h2>
                </CardTitle>
                <CardDescription>
                  Evolución en {actual.unidad} · {etiquetaRango}
                </CardDescription>
              </div>
              <ToggleGroup
                  type="single"
                  value={rango}
                  onValueChange={(v) => v && cambiarRango(v as ClaveRango)}
                  aria-label="Periodo de la gráfica"
                >
                  {RANGOS.map((r) => (
                    <ToggleGroupItem key={r.clave} value={r.clave} aria-label={r.etiqueta}>
                      {r.clave}
                    </ToggleGroupItem>
                  ))}
              </ToggleGroup>
            </CardHeader>
            <CardContent aria-busy={serie.isFetching}>
              {serie.isPending ? (
                <Skeleton className="h-72 w-full" />
              ) : serie.isError ? (
                <ErrorCarga onReintentar={() => serie.refetch()} />
              ) : serie.data.puntos.length === 0 ? (
                <p className="py-16 text-center text-sm text-muted-foreground">
                  No hay precios en este periodo.
                </p>
              ) : (
                <GraficaSerie serie={serie.data} />
              )}
            </CardContent>
          </Card>

          {serie.data && serie.data.puntos.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>
                  <h2>Histórico</h2>
                </CardTitle>
                <CardDescription>
                  Precio diario de {actual.nombre} · {etiquetaRango}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <TablaPrecios serie={serie.data} />
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

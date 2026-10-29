"use client";

import { useMemo, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatoFecha, formatoNumero, formatoVariacion } from "@/lib/formato";
import type { Serie } from "@/lib/tipos";
import { cn } from "@/lib/utils";

type Fila = { fecha: string; valor: number; variacion: number | null };

export function TablaPrecios({ serie }: { serie: Serie }) {
  const [orden, setOrden] = useState<SortingState>([{ id: "fecha", desc: true }]);

  const filas = useMemo<Fila[]>(
    () =>
      serie.puntos.map((p, i) => {
        const valor = Number(p.valor);
        const previo = i > 0 ? Number(serie.puntos[i - 1].valor) : null;
        return {
          fecha: p.fecha,
          valor,
          variacion: previo ? ((valor - previo) / previo) * 100 : null,
        };
      }),
    [serie],
  );

  const columnas = useMemo<ColumnDef<Fila>[]>(
    () => [
      {
        accessorKey: "fecha",
        header: "Fecha",
        cell: ({ getValue }) => formatoFecha(getValue<string>()),
      },
      {
        accessorKey: "valor",
        header: `Valor (${serie.unidad})`,
        cell: ({ getValue }) => formatoNumero(getValue<number>()),
        meta: { numerica: true },
      },
      {
        accessorKey: "variacion",
        header: "Variación diaria",
        sortUndefined: "last",
        cell: ({ getValue }) => {
          const v = getValue<number | null>();
          if (v === null) return <span className="text-muted-foreground">—</span>;
          return (
            <span className={cn(v > 0 && "text-positivo", v < 0 && "text-negativo")}>
              {formatoVariacion(v)} %
            </span>
          );
        },
        meta: { numerica: true },
      },
    ],
    [serie.unidad],
  );

  const tabla = useReactTable({
    data: filas,
    columns: columnas,
    state: { sorting: orden },
    onSortingChange: setOrden,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 10 } },
  });

  const pagina = tabla.getState().pagination.pageIndex + 1;

  return (
    <div className="grid gap-3">
      <Table>
        <caption className="sr-only">Histórico diario de {serie.nombre}</caption>
        <TableHeader>
          {tabla.getHeaderGroups().map((g) => (
            <TableRow key={g.id}>
              {g.headers.map((h) => {
                const numerica = (h.column.columnDef.meta as { numerica?: boolean })?.numerica;
                const dir = h.column.getIsSorted();
                return (
                  <TableHead
                    key={h.id}
                    className={cn(numerica && "text-right")}
                    aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : "none"}
                  >
                    <button
                      type="button"
                      onClick={h.column.getToggleSortingHandler()}
                      className={cn(
                        "inline-flex min-h-8 items-center gap-1 rounded-sm outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring",
                        numerica && "flex-row-reverse",
                      )}
                    >
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {dir === "asc" && <ArrowUp className="size-3.5" aria-hidden />}
                      {dir === "desc" && <ArrowDown className="size-3.5" aria-hidden />}
                    </button>
                  </TableHead>
                );
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {tabla.getRowModel().rows.map((fila) => (
            <TableRow key={fila.id}>
              {fila.getVisibleCells().map((celda) => (
                <TableCell
                  key={celda.id}
                  className={cn(
                    (celda.column.columnDef.meta as { numerica?: boolean })?.numerica &&
                      "tabular text-right",
                  )}
                >
                  {flexRender(celda.column.columnDef.cell, celda.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
        <span>
          {filas.length} registros · página {pagina} de {Math.max(tabla.getPageCount(), 1)}
        </span>
        <div className="flex gap-1">
          <Button
            variant="outline"
            size="icon"
            onClick={() => tabla.previousPage()}
            disabled={!tabla.getCanPreviousPage()}
            aria-label="Página anterior"
          >
            <ChevronLeft />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => tabla.nextPage()}
            disabled={!tabla.getCanNextPage()}
            aria-label="Página siguiente"
          >
            <ChevronRight />
          </Button>
        </div>
      </div>
    </div>
  );
}

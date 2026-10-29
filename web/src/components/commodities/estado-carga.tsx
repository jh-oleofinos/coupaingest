"use client";

import { Clock, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { desdeUtc, esHoyEnMexico, formatoMomento } from "@/lib/formato";

import { useEstadoCarga } from "./consultas";

/** Indica si los datos son de hoy. Nunca deja ver datos viejos sin avisarlo. */
export function EstadoCarga() {
  const { data, isPending, isError } = useEstadoCarga();

  if (isPending) return <Skeleton className="h-6 w-44" />;
  if (isError) return null;

  const exitosa = data.ultima_exitosa?.fin ? desdeUtc(data.ultima_exitosa.fin) : null;
  const fallo = data.ultima?.estado === "fallida";

  if (exitosa && esHoyEnMexico(exitosa) && !fallo) {
    return (
      <Badge variant="outline" className="gap-1.5 py-1 font-normal text-muted-foreground">
        <span aria-hidden className="size-2 rounded-full bg-positivo" />
        Actualizado {formatoMomento(exitosa)}
      </Badge>
    );
  }

  const texto = !exitosa
    ? "Aún no hay cargas registradas"
    : fallo
      ? `Falló la última carga · datos al ${formatoMomento(exitosa)}`
      : `Sin actualizar desde ${formatoMomento(exitosa)}`;

  return (
    <Badge variant="aviso" className="gap-1.5 py-1" role="status">
      {fallo ? <TriangleAlert aria-hidden /> : <Clock aria-hidden />}
      {texto}
    </Badge>
  );
}

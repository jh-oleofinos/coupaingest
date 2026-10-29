"use client";

import { CircleAlert, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function ErrorPortal({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-10 text-center">
      <CircleAlert className="size-10 text-destructive" aria-hidden />
      <h1 className="text-lg font-semibold">No pudimos cargar esta página</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        El servicio no respondió. Inténtalo de nuevo en unos minutos; si el problema sigue,
        avisa al administrador del portal.
      </p>
      <Button variant="outline" onClick={reset}>
        <RefreshCw aria-hidden /> Reintentar
      </Button>
    </div>
  );
}

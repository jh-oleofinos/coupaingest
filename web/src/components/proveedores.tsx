"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

export function Proveedores({ children }: { children: React.ReactNode }) {
  const [cliente] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 60 * 1000,
            refetchOnWindowFocus: true,
            retry: (intentos, error) =>
              intentos < 2 && !(error instanceof ErrorHttp && [401, 403, 404].includes(error.estado)),
          },
        },
      }),
  );
  return <QueryClientProvider client={cliente}>{children}</QueryClientProvider>;
}

export class ErrorHttp extends Error {
  constructor(public readonly estado: number) {
    super(`HTTP ${estado}`);
  }
}

/** fetch para los BFF de /api. Una sesión vencida (401) lleva al login. */
export async function obtenerJson<T>(url: string): Promise<T> {
  const r = await fetch(url, { cache: "no-store" });
  if (r.status === 401) {
    // Recarga completa a propósito: la sesión ya no existe y no debe quedar estado en memoria.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?callbackUrl=${encodeURIComponent(window.location.pathname)}`);
  }
  if (!r.ok) throw new ErrorHttp(r.status);
  return (await r.json()) as T;
}

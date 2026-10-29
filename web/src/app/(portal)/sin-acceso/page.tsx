import type { Metadata } from "next";
import { ShieldAlert } from "lucide-react";

import { EncabezadoPagina } from "@/components/encabezado-pagina";
import { exigirUsuario } from "@/lib/dal";

export const metadata: Metadata = { title: "Sin acceso" };

export default async function SinAcceso() {
  await exigirUsuario();
  return (
    <>
      <EncabezadoPagina titulo="Sin acceso" />
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-10 text-center">
        <ShieldAlert className="size-10 text-muted-foreground" aria-hidden />
        <h2 className="text-lg font-semibold">No tienes acceso a esta sección</h2>
        <p className="max-w-md text-sm text-muted-foreground">
          Si necesitas consultarla, pide al administrador del portal que te asigne el rol
          correspondiente.
        </p>
      </div>
    </>
  );
}

import { NextResponse, type NextRequest } from "next/server";

import { reenviar } from "@/lib/bff";
import { PERMISOS } from "@/lib/permisos";

const CODIGO = /^[a-z0-9_]{1,50}$/;
const FECHA = /^\d{4}-\d{2}-\d{2}$/;

export async function GET(
  req: NextRequest,
  ctx: RouteContext<"/api/commodities/[codigo]/serie">,
) {
  const { codigo } = await ctx.params;
  const desde = req.nextUrl.searchParams.get("desde");
  // Solo se reenvían valores con formato conocido: nada del navegador llega a la API sin validar.
  if (!CODIGO.test(codigo) || (desde !== null && !FECHA.test(desde))) {
    return NextResponse.json({ detail: "Parámetros inválidos." }, { status: 400 });
  }
  const query = desde ? `?desde=${desde}` : "";
  return reenviar(`/commodities/${codigo}/serie${query}`, PERMISOS.commoditiesVer);
}

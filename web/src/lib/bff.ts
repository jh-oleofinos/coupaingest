import "server-only";

import { NextResponse } from "next/server";

import { ErrorApi, llamarApi } from "@/lib/api";
import { obtenerUsuario } from "@/lib/dal";
import type { Permiso } from "@/lib/permisos";

/*
  Backend-for-frontend: los componentes del navegador (TanStack Query) llaman a /api/...
  de Next.js; aquí se verifica la sesión y el permiso, y se reenvía a FastAPI con la
  identidad del usuario. La API vuelve a verificar el permiso con la base.
*/
export async function reenviar(ruta: string, permiso: Permiso): Promise<NextResponse> {
  try {
    const usuario = await obtenerUsuario();
    if (!usuario) return NextResponse.json({ detail: "No autenticado." }, { status: 401 });
    if (!usuario.permisos.includes(permiso)) {
      return NextResponse.json({ detail: "Sin permiso." }, { status: 403 });
    }
    const datos = await llamarApi<unknown>(ruta, usuario.identidad);
    return NextResponse.json(datos);
  } catch (e) {
    const estado = e instanceof ErrorApi && [401, 403, 404, 422].includes(e.estado) ? e.estado : 502;
    if (estado === 502) console.error(`BFF ${ruta}`, e);
    return NextResponse.json({ detail: "No se pudo obtener la información." }, { status: estado });
  }
}

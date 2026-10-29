import { redirect } from "next/navigation";

import { exigirUsuario } from "@/lib/dal";
import { MODULOS } from "@/lib/navegacion";

/** Inicio: lleva al primer módulo que el usuario puede ver. */
export default async function Inicio() {
  const usuario = await exigirUsuario();
  const primero = MODULOS.flatMap((m) => m.opciones).find((o) =>
    usuario.permisos.includes(o.permiso),
  );
  redirect(primero?.href ?? "/sin-acceso");
}

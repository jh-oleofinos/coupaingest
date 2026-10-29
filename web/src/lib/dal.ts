import "server-only";

import { cache } from "react";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { ErrorApi, llamarApi, type Identidad } from "@/lib/api";
import type { Permiso } from "@/lib/permisos";
import type { Perfil, Rol } from "@/lib/tipos";

/*
  Capa de acceso a datos (DAL): único lugar donde la web decide quién es el usuario y qué
  puede ver. Toda página, Server Action y Route Handler pasa por aquí. El proxy solo hace
  una redirección optimista y no se usa como control de acceso.

  En cada petición se pide el perfil a la API: un cambio de rol, una baja o un cierre de
  sesión en otro equipo se reflejan de inmediato.
*/

export type UsuarioSesion = {
  id: string;
  nombre: string;
  correo: string;
  roles: Rol[];
  permisos: string[];
  identidad: Identidad;
};

export const obtenerUsuario = cache(async (): Promise<UsuarioSesion | null> => {
  const sesion = await auth();
  const u = sesion?.user;
  if (!u?.id || typeof u.vs !== "number" || u.vs < 0) return null;

  const identidad: Identidad = { tipo: "usuario", usuarioId: u.id, versionSesion: u.vs };
  try {
    const perfil = await llamarApi<Perfil>("/auth/perfil", identidad);
    return {
      id: String(perfil.id),
      nombre: perfil.nombre,
      correo: perfil.correo,
      roles: perfil.roles,
      permisos: perfil.permisos,
      identidad,
    };
  } catch (e) {
    // 401: sesión cerrada, usuario dado de baja o versión vieja → como si no hubiera sesión.
    if (e instanceof ErrorApi && e.estado === 401) return null;
    throw e; // API caída: se muestra la página de error, nunca datos sin verificar.
  }
});

/** Para páginas: sin sesión → /login; sin permiso → /sin-acceso. */
export async function exigirUsuario(permiso?: Permiso): Promise<UsuarioSesion> {
  const usuario = await obtenerUsuario();
  if (!usuario) redirect("/login");
  if (permiso && !usuario.permisos.includes(permiso)) redirect("/sin-acceso");
  return usuario;
}

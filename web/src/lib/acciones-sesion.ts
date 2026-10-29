"use server";

import { AuthError, CredentialsSignin } from "next-auth";
import { z } from "zod";

import { signIn, signOut } from "@/auth";
import { llamarApi } from "@/lib/api";
import { obtenerUsuario } from "@/lib/dal";

export type EstadoLogin = { error: string } | null;

const schema = z.object({
  correo: z.email().max(254),
  contrasena: z.string().min(1).max(128),
});

/** Solo rutas internas: evita redirecciones abiertas hacia otros sitios. */
function destinoSeguro(valor: FormDataEntryValue | null): string {
  const v = typeof valor === "string" ? valor : "";
  return v.startsWith("/") && !v.startsWith("//") && !v.startsWith("/\\") ? v : "/";
}

export async function iniciarSesion(_: EstadoLogin, fd: FormData): Promise<EstadoLogin> {
  const datos = schema.safeParse({ correo: fd.get("correo"), contrasena: fd.get("contrasena") });
  if (!datos.success) return { error: "Revisa el correo y la contraseña." };

  try {
    await signIn("credentials", { ...datos.data, redirectTo: destinoSeguro(fd.get("callbackUrl")) });
  } catch (e) {
    if (e instanceof CredentialsSignin && e.code === "servicio") {
      return { error: "No pudimos validar tu acceso en este momento. Intenta de nuevo en unos minutos." };
    }
    if (e instanceof AuthError) {
      return {
        error:
          "Correo o contraseña incorrectos. Después de varios intentos fallidos, la cuenta se bloquea 15 minutos.",
      };
    }
    throw e; // la redirección de éxito de Next.js también llega como excepción
  }
  return null;
}

export async function iniciarSesionMicrosoft(fd: FormData): Promise<void> {
  await signIn("microsoft-entra-id", { redirectTo: destinoSeguro(fd.get("callbackUrl")) });
}

export async function cerrarSesion(): Promise<void> {
  const usuario = await obtenerUsuario();
  if (usuario) {
    try {
      // Invalida la sesión en la API: una copia de la cookie ya no sirve de nada.
      await llamarApi("/auth/cerrar-sesion", usuario.identidad, { metodo: "POST" });
    } catch (e) {
      console.error("No se pudo invalidar la sesión en la API", e);
    }
  }
  await signOut({ redirectTo: "/login" });
}

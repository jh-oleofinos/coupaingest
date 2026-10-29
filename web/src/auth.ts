import NextAuth, { CredentialsSignin, type NextAuthConfig, type User } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";
import { z } from "zod";

import { ErrorApi, llamarApi } from "@/lib/api";
import { entraHabilitado, env, tenantEntra } from "@/lib/env";
import type { Perfil } from "@/lib/tipos";

/*
  Identidad (quién eres): usuario y contraseña validados por la API, o Entra ID si está configurado.
  Autorización (qué puedes ver): siempre los roles y permisos de la base del portal, que la capa
  de acceso (lib/dal.ts) vuelve a pedir a la API en cada página.

  La cookie de sesión (JWT cifrado, HttpOnly) solo guarda: id, nombre, correo, versión de sesión
  y hora de inicio. Vence a las 8 h de inactividad y, como máximo, 8 h después del inicio.
  Al cerrar sesión la API sube la versión de sesión y cualquier cookie anterior deja de servir.
*/

const DURACION_SESION_S = 8 * 60 * 60;
const SERVICIO = { tipo: "servicio" } as const;

class ServicioNoDisponible extends CredentialsSignin {
  code = "servicio";
}

const credencialesSchema = z.object({
  correo: z.email().max(254),
  contrasena: z.string().min(1).max(128),
});

type UsuarioConPerfil = User & { perfil?: Perfil };

function datosDeSesion(perfil: Perfil) {
  return {
    sub: String(perfil.id),
    name: perfil.nombre,
    email: perfil.correo,
    vs: perfil.version_sesion,
    iniciadoEn: Date.now(),
  };
}

/** Datos de Entra validados: el usuario debe venir de NUESTRO tenant. */
function identidadEntra(profile: Record<string, unknown> | undefined) {
  const tid = String(profile?.tid ?? "").toLowerCase();
  const oid = String(profile?.oid ?? "");
  const correo = String(profile?.email ?? profile?.preferred_username ?? "");
  if (!tid || tid !== tenantEntra() || !oid || !correo) return null;
  return { oid, correo };
}

function configuracion(): NextAuthConfig {
  const providers: NextAuthConfig["providers"] = [
    Credentials({
      id: "credentials",
      credentials: { correo: {}, contrasena: {} },
      async authorize(entrada): Promise<UsuarioConPerfil | null> {
        const datos = credencialesSchema.safeParse(entrada);
        if (!datos.success) return null;
        try {
          const perfil = await llamarApi<Perfil>("/auth/login", SERVICIO, {
            metodo: "POST",
            cuerpo: datos.data,
          });
          return { id: String(perfil.id), name: perfil.nombre, email: perfil.correo, perfil };
        } catch (e) {
          if (e instanceof ErrorApi && e.estado === 401) return null;
          console.error("Login: la API no respondió", e);
          throw new ServicioNoDisponible();
        }
      },
    }),
  ];

  if (entraHabilitado()) {
    providers.push(
      MicrosoftEntraID({
        clientId: env().AUTH_MICROSOFT_ENTRA_ID_ID,
        clientSecret: env().AUTH_MICROSOFT_ENTRA_ID_SECRET,
        issuer: env().AUTH_MICROSOFT_ENTRA_ID_ISSUER,
      }),
    );
  }

  return {
    secret: env().AUTH_SECRET,
    trustHost: true,
    providers,
    pages: { signIn: "/login", error: "/login" },
    session: { strategy: "jwt", maxAge: DURACION_SESION_S },
    callbacks: {
      async signIn({ user, account, profile }) {
        if (account?.provider !== "microsoft-entra-id") return true;
        // Entra ya autenticó a la persona; el portal decide si está autorizada.
        const identidad = identidadEntra(profile as Record<string, unknown> | undefined);
        if (!identidad) return false;
        try {
          (user as UsuarioConPerfil).perfil = await llamarApi<Perfil>("/auth/entra", SERVICIO, {
            metodo: "POST",
            cuerpo: identidad,
          });
          return true;
        } catch {
          return false; // → /login?error=AccessDenied
        }
      },

      async jwt({ token, user, account, profile }) {
        if (account && user) {
          let perfil = (user as UsuarioConPerfil).perfil;
          if (!perfil && account.provider === "microsoft-entra-id") {
            const identidad = identidadEntra(profile as Record<string, unknown> | undefined);
            if (!identidad) return null;
            perfil = await llamarApi<Perfil>("/auth/entra", SERVICIO, {
              metodo: "POST",
              cuerpo: identidad,
            });
          }
          if (!perfil) return null;
          return { ...datosDeSesion(perfil), iat: token.iat, exp: token.exp, jti: token.jti };
        }
        // Vencimiento absoluto: la cookie se renueva con el uso, pero la sesión no pasa de 8 h.
        if (!token.iniciadoEn || Date.now() - token.iniciadoEn > DURACION_SESION_S * 1000) {
          return null;
        }
        return token;
      },

      async session({ session, token }) {
        // Solo identificadores; roles y permisos se piden a la API en cada página (lib/dal.ts).
        session.user = {
          ...session.user,
          id: token.sub ?? "",
          name: token.name ?? "",
          email: token.email ?? "",
          vs: token.vs ?? -1,
        };
        return session;
      },
    },
  };
}

export const { handlers, auth, signIn, signOut } = NextAuth(() => configuracion());

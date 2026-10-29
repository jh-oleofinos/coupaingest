import type { DefaultSession } from "next-auth";
import type {} from "@auth/core/jwt";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      /** Versión de sesión: si no coincide con la de la base, la API rechaza la petición. */
      vs: number;
    } & DefaultSession["user"];
  }
}

declare module "@auth/core/jwt" {
  interface JWT {
    vs?: number;
    iniciadoEn?: number;
  }
}

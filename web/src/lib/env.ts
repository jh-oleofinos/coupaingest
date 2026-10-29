import "server-only";

import { z } from "zod";

/*
  Variables del servidor. Ninguna se expone al navegador (no usan el prefijo NEXT_PUBLIC_).
  En el servidor de Windows se cargan desde el Administrador de credenciales al arrancar
  el servicio (ver docs/despliegue-windows.md); en desarrollo, desde .env.local.
*/
const esquema = z
  .object({
    AUTH_SECRET: z.string().min(32, "AUTH_SECRET debe tener al menos 32 caracteres."),
    API_URL: z
      .url()
      .refine(
        (u) => ["127.0.0.1", "localhost"].includes(new URL(u).hostname),
        "API_URL debe apuntar a localhost: la API no se expone fuera del servidor.",
      ),
    API_TOKEN_SECRET: z.string().min(32, "API_TOKEN_SECRET debe tener al menos 32 caracteres."),
    // Entra ID: opcional. Si faltan, solo se muestra el login con usuario y contraseña.
    AUTH_MICROSOFT_ENTRA_ID_ID: z.string().optional(),
    AUTH_MICROSOFT_ENTRA_ID_SECRET: z.string().optional(),
    // Debe ser el issuer de NUESTRO tenant (con su GUID), nunca /common ni /organizations.
    AUTH_MICROSOFT_ENTRA_ID_ISSUER: z
      .url()
      .regex(
        /^https:\/\/login\.microsoftonline\.com\/[0-9a-f-]{36}\/v2\.0\/?$/i,
        "AUTH_MICROSOFT_ENTRA_ID_ISSUER debe ser https://login.microsoftonline.com/<tenant-id>/v2.0",
      )
      .optional(),
  })
  .refine(
    (e) =>
      [e.AUTH_MICROSOFT_ENTRA_ID_ID, e.AUTH_MICROSOFT_ENTRA_ID_SECRET, e.AUTH_MICROSOFT_ENTRA_ID_ISSUER]
        .filter(Boolean).length % 3 === 0,
    "Entra ID requiere las tres variables AUTH_MICROSOFT_ENTRA_ID_* o ninguna.",
  );

function cargar() {
  const r = esquema.safeParse(process.env);
  if (!r.success) {
    throw new Error(
      "Configuración inválida:\n" + r.error.issues.map((i) => `- ${i.message}`).join("\n"),
    );
  }
  return r.data;
}

let cache: z.infer<typeof esquema> | null = null;

export function env() {
  cache ??= cargar();
  return cache;
}

export function entraHabilitado(): boolean {
  return Boolean(env().AUTH_MICROSOFT_ENTRA_ID_ID);
}

/** GUID del tenant de Oleofinos, tomado del issuer. */
export function tenantEntra(): string | null {
  const issuer = env().AUTH_MICROSOFT_ENTRA_ID_ISSUER;
  return issuer ? issuer.split("/")[3].toLowerCase() : null;
}

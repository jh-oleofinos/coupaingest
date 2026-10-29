import "server-only";

import { SignJWT } from "jose";

import { env } from "@/lib/env";

/*
  Cliente de la API de FastAPI. Solo corre en el servidor de Next.js.
  Cada llamada lleva un JWT HS256 de 60 s firmado con API_TOKEN_SECRET:
    - "servicio": login y resolución de usuarios de Entra (aún no hay usuario).
    - "usuario": todo lo demás; la API vuelve a leer al usuario y sus permisos de la base.
*/

export type Identidad =
  | { tipo: "servicio" }
  | { tipo: "usuario"; usuarioId: string; versionSesion: number };

export class ErrorApi extends Error {
  constructor(
    public readonly estado: number,
    mensaje: string,
  ) {
    super(mensaje);
  }
}

const VIDA_TOKEN_SEGUNDOS = 60;

async function firmar(identidad: Identidad): Promise<string> {
  const secreto = new TextEncoder().encode(env().API_TOKEN_SECRET);
  const claims =
    identidad.tipo === "usuario"
      ? { typ: identidad.tipo, vs: identidad.versionSesion }
      : { typ: identidad.tipo };
  return new SignJWT(claims)
    .setProtectedHeader({ alg: "HS256" })
    .setIssuer("oleoweb-web")
    .setAudience("oleoweb-api")
    .setSubject(identidad.tipo === "usuario" ? identidad.usuarioId : "web")
    .setIssuedAt()
    .setExpirationTime(`${VIDA_TOKEN_SEGUNDOS}s`)
    .sign(secreto);
}

export async function llamarApi<T>(
  ruta: string,
  identidad: Identidad,
  opciones: { metodo?: "GET" | "POST"; cuerpo?: unknown } = {},
): Promise<T> {
  const url = new URL(ruta, env().API_URL);
  const respuesta = await fetch(url, {
    method: opciones.metodo ?? "GET",
    headers: {
      Authorization: `Bearer ${await firmar(identidad)}`,
      ...(opciones.cuerpo !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: opciones.cuerpo !== undefined ? JSON.stringify(opciones.cuerpo) : undefined,
    cache: "no-store",
    signal: AbortSignal.timeout(15_000),
  });
  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, `API ${ruta} respondió ${respuesta.status}`);
  }
  return (await respuesta.json()) as T;
}

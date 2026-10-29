import { NextResponse, type NextFetchEvent, type NextRequest } from "next/server";

import { auth } from "@/auth";

/*
  Proxy (antes "middleware"):
  1. Política de seguridad de contenido (CSP) con nonce por petición.
  2. Redirección OPTIMISTA a /login si no hay sesión. No es el control de acceso:
     cada página y endpoint vuelve a verificar la sesión y el permiso (lib/dal.ts).
*/

const RUTAS_PUBLICAS = ["/login"];

function politicaCsp(nonce: string): string {
  const dev = process.env.NODE_ENV === "development";
  const conHttps = (process.env.AUTH_URL ?? "").startsWith("https://");
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${dev ? " 'unsafe-eval'" : ""}`,
    // Radix y Recharts usan atributos style en línea; los scripts siguen protegidos por nonce.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' blob: data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self' https://login.microsoftonline.com",
    "frame-ancestors 'none'",
    ...(conHttps ? ["upgrade-insecure-requests"] : []),
  ].join("; ");
}

// Con configuración diferida (auth.ts), auth(fn) devuelve una promesa del manejador.
const conSesion = auth((req) => {
  const { pathname, search } = req.nextUrl;
  const publica = RUTAS_PUBLICAS.some((r) => pathname === r || pathname.startsWith(`${r}/`));

  if (!req.auth && !publica) {
    const destino = new URL("/login", req.nextUrl);
    if (pathname !== "/") destino.searchParams.set("callbackUrl", `${pathname}${search}`);
    return NextResponse.redirect(destino);
  }

  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = politicaCsp(nonce);
  const cabeceras = new Headers(req.headers);
  cabeceras.set("x-nonce", nonce);
  cabeceras.set("Content-Security-Policy", csp);

  const respuesta = NextResponse.next({ request: { headers: cabeceras } });
  respuesta.headers.set("Content-Security-Policy", csp);
  return respuesta;
});

type Manejador = (req: NextRequest, evento: NextFetchEvent) => Promise<Response>;

export async function proxy(req: NextRequest, evento: NextFetchEvent) {
  const manejar = (await (conSesion as unknown as Promise<Manejador>)) as Manejador;
  return manejar(req, evento);
}

export const config = {
  matcher: [
    {
      // Todo excepto la API de Auth.js, los BFF (/api, verifican sesión ellos mismos) y estáticos.
      source: "/((?!api/|_next/static/|_next/image|favicon\\.ico$).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};

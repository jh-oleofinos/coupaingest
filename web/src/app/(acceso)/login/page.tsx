import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { CircleAlert } from "lucide-react";

import { Logo } from "@/components/logo";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { obtenerUsuario } from "@/lib/dal";
import { entraHabilitado } from "@/lib/env";

import { BotonMicrosoft, FormularioLogin } from "./formulario-login";

export const metadata: Metadata = { title: "Iniciar sesión" };

const ERRORES: Record<string, string> = {
  AccessDenied: "Tu cuenta no tiene acceso al portal. Pide acceso al administrador.",
  Configuration: "El inicio de sesión no está disponible en este momento. Intenta más tarde.",
};

export default async function PaginaLogin({ searchParams }: PageProps<"/login">) {
  // Si la API no responde se muestra el formulario; el login dará el aviso correspondiente.
  const usuario = await obtenerUsuario().catch(() => null);
  if (usuario) redirect("/");

  const params = await searchParams;
  const callbackUrl = typeof params.callbackUrl === "string" ? params.callbackUrl : "/";
  const codigoError = typeof params.error === "string" ? params.error : undefined;
  const error = codigoError ? (ERRORES[codigoError] ?? ERRORES.Configuration) : undefined;
  const conMicrosoft = entraHabilitado();

  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/40 px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <Logo tamano="lg" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Portal Oleofinos</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Inicia sesión con tu cuenta para continuar.
            </p>
          </div>
        </div>

        <div className="rounded-xl border bg-card p-6 shadow-sm">
          {error && (
            <Alert variant="destructive" className="mb-5">
              <CircleAlert aria-hidden />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <FormularioLogin callbackUrl={callbackUrl} />

          {conMicrosoft && (
            <>
              <div className="my-5 flex items-center gap-3 text-xs text-muted-foreground">
                <span className="h-px flex-1 bg-border" />o<span className="h-px flex-1 bg-border" />
              </div>
              <BotonMicrosoft callbackUrl={callbackUrl} />
            </>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Acceso restringido a personal autorizado. Los accesos quedan registrados.
        </p>
      </div>
    </main>
  );
}

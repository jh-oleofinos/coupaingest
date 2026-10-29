"use client";

import { startTransition, useActionState, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { CircleAlert, Eye, EyeOff, LoaderCircle } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { iniciarSesion, iniciarSesionMicrosoft } from "@/lib/acciones-sesion";

const schema = z.object({
  correo: z.email("Escribe un correo válido.").max(254),
  contrasena: z.string().min(1, "Escribe tu contraseña.").max(128),
});
type Campos = z.infer<typeof schema>;

export function FormularioLogin({ callbackUrl }: { callbackUrl: string }) {
  const [estado, accion, enviando] = useActionState(iniciarSesion, null);
  const [verContrasena, setVerContrasena] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Campos>({ resolver: zodResolver(schema), mode: "onTouched" });

  const enviar = handleSubmit((valores) => {
    const fd = new FormData();
    fd.set("correo", valores.correo);
    fd.set("contrasena", valores.contrasena);
    fd.set("callbackUrl", callbackUrl);
    startTransition(() => accion(fd));
  });

  return (
    <form onSubmit={enviar} noValidate className="grid gap-5">
      {estado?.error && (
        <Alert variant="destructive" aria-live="polite">
          <CircleAlert aria-hidden />
          <AlertDescription>{estado.error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-2">
        <Label htmlFor="correo">Correo</Label>
        <Input
          id="correo"
          type="email"
          autoComplete="username"
          inputMode="email"
          placeholder="nombre@oleofinos.com.mx"
          aria-invalid={Boolean(errors.correo)}
          aria-describedby={errors.correo ? "correo-error" : undefined}
          {...register("correo")}
        />
        {errors.correo && (
          <p id="correo-error" className="text-sm text-destructive">
            {errors.correo.message}
          </p>
        )}
      </div>

      <div className="grid gap-2">
        <Label htmlFor="contrasena">Contraseña</Label>
        <div className="relative">
          <Input
            id="contrasena"
            type={verContrasena ? "text" : "password"}
            autoComplete="current-password"
            className="pr-11"
            aria-invalid={Boolean(errors.contrasena)}
            aria-describedby={errors.contrasena ? "contrasena-error" : undefined}
            {...register("contrasena")}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="absolute top-1 right-1 text-muted-foreground"
            onClick={() => setVerContrasena((v) => !v)}
            aria-label={verContrasena ? "Ocultar contraseña" : "Mostrar contraseña"}
            aria-pressed={verContrasena}
          >
            {verContrasena ? <EyeOff /> : <Eye />}
          </Button>
        </div>
        {errors.contrasena && (
          <p id="contrasena-error" className="text-sm text-destructive">
            {errors.contrasena.message}
          </p>
        )}
      </div>

      <Button type="submit" size="lg" className="w-full" disabled={enviando}>
        {enviando && <LoaderCircle className="animate-spin" aria-hidden />}
        {enviando ? "Iniciando sesión…" : "Iniciar sesión"}
      </Button>
    </form>
  );
}

export function BotonMicrosoft({ callbackUrl }: { callbackUrl: string }) {
  return (
    <form action={iniciarSesionMicrosoft}>
      <input type="hidden" name="callbackUrl" value={callbackUrl} />
      <Button type="submit" variant="outline" size="lg" className="w-full">
        Continuar con Microsoft
      </Button>
    </form>
  );
}

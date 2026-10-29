import { cn } from "@/lib/utils";

/*
  Logo PROVISIONAL. Cuando llegue el logo oficial de Oleofinos:
  1. Copia el archivo a web/public/logo.svg (o .png con fondo transparente).
  2. Reemplaza el contenido de este componente por:
       <Image src="/logo.svg" alt="Oleofinos" width={...} height={...} priority />
  Todo el portal usa este componente, así que no hay que tocar nada más.
*/
export function Logo({
  tamano = "md",
  soloIcono = false,
  className,
}: {
  tamano?: "md" | "lg";
  soloIcono?: boolean;
  className?: string;
}) {
  const caja = tamano === "lg" ? "size-12 text-xl" : "size-8 text-sm";
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span
        aria-hidden
        className={cn(
          "flex shrink-0 items-center justify-center rounded-lg bg-primary font-bold text-primary-foreground",
          caja,
        )}
      >
        O
      </span>
      {soloIcono ? (
        <span className="sr-only">Oleofinos</span>
      ) : (
        tamano !== "lg" && <span className="truncate font-semibold">Oleofinos</span>
      )}
      {tamano === "lg" && <span className="sr-only">Oleofinos</span>}
    </span>
  );
}

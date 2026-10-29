import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";

export function EncabezadoPagina({
  titulo,
  descripcion,
  acciones,
}: {
  titulo: string;
  descripcion?: string;
  acciones?: React.ReactNode;
}) {
  return (
    <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
      <div className="flex min-h-14 flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2 md:px-6">
        <SidebarTrigger className="-ml-1.5" />
        <Separator orientation="vertical" className="h-5!" />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-semibold leading-tight">{titulo}</h1>
          {descripcion && (
            <p className="truncate text-sm text-muted-foreground">{descripcion}</p>
          )}
        </div>
        {acciones && <div className="basis-full sm:basis-auto">{acciones}</div>}
      </div>
    </header>
  );
}

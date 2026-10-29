"use client";

/*
  Sidebar basado en el componente Sidebar de shadcn/ui (misma API, versión reducida):
  colapsable a íconos en escritorio, panel lateral en celular, atajo Ctrl/⌘+B y
  estado recordado en una cookie no sensible.
*/

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { PanelLeftIcon } from "lucide-react";
import { Slot } from "radix-ui";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const COOKIE_SIDEBAR = "sidebar_state";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365;
const ANCHO = "16rem";
const ANCHO_MOVIL = "18rem";
const ANCHO_ICONO = "3rem";
const ATAJO = "b";
const PUNTO_MOVIL = 768;

type ContextoSidebar = {
  estado: "expandido" | "colapsado";
  abierto: boolean;
  setAbierto: (abierto: boolean) => void;
  abiertoMovil: boolean;
  setAbiertoMovil: (abierto: boolean) => void;
  esMovil: boolean;
  alternar: () => void;
};

const SidebarContext = React.createContext<ContextoSidebar | null>(null);

function useSidebar() {
  const ctx = React.useContext(SidebarContext);
  if (!ctx) throw new Error("useSidebar debe usarse dentro de SidebarProvider.");
  return ctx;
}

function useEsMovil() {
  const [esMovil, setEsMovil] = React.useState(false);
  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${PUNTO_MOVIL - 1}px)`);
    const actualizar = () => setEsMovil(mql.matches);
    actualizar();
    mql.addEventListener("change", actualizar);
    return () => mql.removeEventListener("change", actualizar);
  }, []);
  return esMovil;
}

function SidebarProvider({
  defaultOpen = true,
  className,
  style,
  children,
  ...props
}: React.ComponentProps<"div"> & { defaultOpen?: boolean }) {
  const esMovil = useEsMovil();
  const [abiertoMovil, setAbiertoMovil] = React.useState(false);
  const [abierto, _setAbierto] = React.useState(defaultOpen);

  const setAbierto = React.useCallback((valor: boolean) => {
    _setAbierto(valor);
    document.cookie = `${COOKIE_SIDEBAR}=${valor}; path=/; max-age=${COOKIE_MAX_AGE}; samesite=lax`;
  }, []);

  const alternar = React.useCallback(() => {
    if (esMovil) setAbiertoMovil((v) => !v);
    else setAbierto(!abierto);
  }, [esMovil, abierto, setAbierto]);

  React.useEffect(() => {
    const alPresionar = (e: KeyboardEvent) => {
      if (e.key === ATAJO && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        alternar();
      }
    };
    window.addEventListener("keydown", alPresionar);
    return () => window.removeEventListener("keydown", alPresionar);
  }, [alternar]);

  const valor = React.useMemo<ContextoSidebar>(
    () => ({
      estado: abierto ? "expandido" : "colapsado",
      abierto,
      setAbierto,
      esMovil,
      abiertoMovil,
      setAbiertoMovil,
      alternar,
    }),
    [abierto, setAbierto, esMovil, abiertoMovil, alternar],
  );

  return (
    <SidebarContext.Provider value={valor}>
      <TooltipProvider delayDuration={0}>
        <div
          data-slot="sidebar-wrapper"
          style={
            {
              "--sidebar-width": ANCHO,
              "--sidebar-width-icon": ANCHO_ICONO,
              ...style,
            } as React.CSSProperties
          }
          className={cn("group/sidebar-wrapper flex min-h-svh w-full", className)}
          {...props}
        >
          {children}
        </div>
      </TooltipProvider>
    </SidebarContext.Provider>
  );
}

function Sidebar({ className, children, ...props }: React.ComponentProps<"div">) {
  const { esMovil, estado, abiertoMovil, setAbiertoMovil } = useSidebar();

  if (esMovil) {
    return (
      <Sheet open={abiertoMovil} onOpenChange={setAbiertoMovil}>
        <SheetContent
          data-sidebar="sidebar"
          data-slot="sidebar"
          data-mobile="true"
          className="w-(--sidebar-width) bg-sidebar p-0 text-sidebar-foreground [&>button]:hidden"
          style={{ "--sidebar-width": ANCHO_MOVIL } as React.CSSProperties}
          side="left"
        >
          <SheetHeader className="sr-only">
            <SheetTitle>Menú</SheetTitle>
            <SheetDescription>Navegación del portal.</SheetDescription>
          </SheetHeader>
          <div className="flex h-full w-full flex-col">{children}</div>
        </SheetContent>
      </Sheet>
    );
  }

  const colapsado = estado === "colapsado";
  return (
    <aside
      aria-label={props["aria-label"]}
      className="group peer hidden text-sidebar-foreground md:block"
      data-state={colapsado ? "collapsed" : "expanded"}
      data-collapsible={colapsado ? "icon" : ""}
      data-slot="sidebar"
    >
      {/* Reserva el espacio del sidebar fijo */}
      <div
        className={cn(
          "relative w-(--sidebar-width) bg-transparent transition-[width] duration-200 ease-linear",
          "group-data-[collapsible=icon]:w-(--sidebar-width-icon)",
        )}
      />
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-10 hidden h-svh w-(--sidebar-width) border-r transition-[width] duration-200 ease-linear md:flex",
          "group-data-[collapsible=icon]:w-(--sidebar-width-icon)",
          className,
        )}
        {...props}
      >
        <div
          data-sidebar="sidebar"
          className="flex h-full w-full flex-col bg-sidebar"
        >
          {children}
        </div>
      </div>
    </aside>
  );
}

function SidebarTrigger({ className, onClick, ...props }: React.ComponentProps<typeof Button>) {
  const { alternar, abierto, esMovil, abiertoMovil } = useSidebar();
  return (
    <Button
      data-sidebar="trigger"
      variant="ghost"
      size="icon"
      className={className}
      aria-label="Mostrar u ocultar el menú"
      aria-expanded={esMovil ? abiertoMovil : abierto}
      onClick={(e) => {
        onClick?.(e);
        alternar();
      }}
      {...props}
    >
      <PanelLeftIcon />
    </Button>
  );
}

function SidebarInset({ className, ...props }: React.ComponentProps<"main">) {
  return (
    <main
      data-slot="sidebar-inset"
      className={cn("relative flex w-full min-w-0 flex-1 flex-col bg-background", className)}
      {...props}
    />
  );
}

function SidebarHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div data-sidebar="header" className={cn("flex flex-col gap-2 p-2", className)} {...props} />
  );
}

function SidebarFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div data-sidebar="footer" className={cn("flex flex-col gap-2 p-2", className)} {...props} />
  );
}

function SidebarSeparator({ className, ...props }: React.ComponentProps<typeof Separator>) {
  return (
    <Separator
      data-sidebar="separator"
      className={cn("mx-2 w-auto bg-sidebar-border", className)}
      {...props}
    />
  );
}

function SidebarContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-sidebar="content"
      className={cn(
        "flex min-h-0 flex-1 flex-col gap-2 overflow-auto group-data-[collapsible=icon]:overflow-hidden",
        className,
      )}
      {...props}
    />
  );
}

function SidebarGroup({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-sidebar="group"
      className={cn("relative flex w-full min-w-0 flex-col p-2", className)}
      {...props}
    />
  );
}

function SidebarGroupLabel({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-sidebar="group-label"
      className={cn(
        "flex h-8 shrink-0 items-center rounded-md px-2 text-xs font-medium text-sidebar-foreground/70 transition-[margin,opacity] duration-200 ease-linear",
        "group-data-[collapsible=icon]:-mt-8 group-data-[collapsible=icon]:opacity-0",
        className,
      )}
      {...props}
    />
  );
}

function SidebarMenu({ className, ...props }: React.ComponentProps<"ul">) {
  return (
    <ul
      data-sidebar="menu"
      className={cn("flex w-full min-w-0 flex-col gap-1", className)}
      {...props}
    />
  );
}

function SidebarMenuItem({ className, ...props }: React.ComponentProps<"li">) {
  return (
    <li data-sidebar="menu-item" className={cn("group/menu-item relative", className)} {...props} />
  );
}

const sidebarMenuButtonVariants = cva(
  "peer/menu-button flex w-full items-center gap-2 overflow-hidden rounded-md p-2 text-left text-sm outline-hidden ring-sidebar-ring transition-[width,height,padding] hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 active:bg-sidebar-accent disabled:pointer-events-none disabled:opacity-50 data-[active=true]:bg-sidebar-accent data-[active=true]:font-medium data-[active=true]:text-sidebar-accent-foreground group-data-[collapsible=icon]:size-8! group-data-[collapsible=icon]:p-2! [&>span:last-child]:truncate [&>svg]:size-4 [&>svg]:shrink-0",
  {
    variants: {
      size: {
        default: "h-8 text-sm",
        lg: "h-12 text-sm group-data-[collapsible=icon]:p-0!",
      },
    },
    defaultVariants: { size: "default" },
  },
);

function SidebarMenuButton({
  asChild = false,
  isActive = false,
  tooltip,
  size,
  className,
  ...props
}: React.ComponentProps<"button"> & {
  asChild?: boolean;
  isActive?: boolean;
  tooltip?: string;
} & VariantProps<typeof sidebarMenuButtonVariants>) {
  const Comp = asChild ? Slot.Root : "button";
  const { esMovil, estado } = useSidebar();

  const boton = (
    <Comp
      data-sidebar="menu-button"
      data-size={size}
      data-active={isActive}
      aria-current={isActive ? "page" : undefined}
      className={cn(sidebarMenuButtonVariants({ size }), className)}
      {...props}
    />
  );

  if (!tooltip) return boton;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{boton}</TooltipTrigger>
      <TooltipContent side="right" align="center" hidden={estado !== "colapsado" || esMovil}>
        {tooltip}
      </TooltipContent>
    </Tooltip>
  );
}

export {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarSeparator,
  SidebarTrigger,
  useSidebar,
};

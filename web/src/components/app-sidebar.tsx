"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";

import { Logo } from "@/components/logo";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";
import { cerrarSesion } from "@/lib/acciones-sesion";
import { MODULOS } from "@/lib/navegacion";
import type { Rol } from "@/lib/tipos";
import { cn } from "@/lib/utils";

type Props = { usuario: { nombre: string; correo: string; roles: Rol[]; permisos: string[] } };

function iniciales(nombre: string): string {
  const partes = nombre.trim().split(/\s+/);
  return ((partes[0]?.[0] ?? "") + (partes.length > 1 ? partes.at(-1)![0] : "")).toUpperCase();
}

export function AppSidebar({ usuario }: Props) {
  const ruta = usePathname();
  const { estado, esMovil, setAbiertoMovil } = useSidebar();
  const colapsado = estado === "colapsado" && !esMovil;
  const rol = usuario.roles.map((r) => r.nombre).join(", ") || "Sin rol";

  const modulos = MODULOS.map((m) => ({
    ...m,
    opciones: m.opciones.filter((o) => usuario.permisos.includes(o.permiso)),
  })).filter((m) => m.opciones.length > 0);

  return (
    <Sidebar aria-label="Menú principal">
      <SidebarHeader className="h-14 justify-center border-b px-3 group-data-[collapsible=icon]:px-2">
        <Link href="/" className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring">
          <Logo soloIcono={colapsado} />
        </Link>
      </SidebarHeader>

      <SidebarContent>
        <nav aria-label="Módulos">
          {modulos.map((modulo) => (
            <SidebarGroup key={modulo.titulo}>
              <SidebarGroupLabel>{modulo.titulo}</SidebarGroupLabel>
              <SidebarMenu>
                {modulo.opciones.map((o) => (
                  <SidebarMenuItem key={o.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={ruta === o.href || ruta.startsWith(`${o.href}/`)}
                      tooltip={`${modulo.titulo}: ${o.titulo}`}
                    >
                      <Link href={o.href} onClick={() => esMovil && setAbiertoMovil(false)}>
                        <o.icono aria-hidden />
                        <span>{o.titulo}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroup>
          ))}
        </nav>
      </SidebarContent>

      <SidebarSeparator />
      <SidebarFooter>
        <div
          className={cn(
            "flex items-center gap-3 rounded-md px-1 py-1.5",
            colapsado && "justify-center px-0",
          )}
          title={colapsado ? `${usuario.nombre} · ${rol}` : undefined}
        >
          <Avatar className="size-9">
            <AvatarFallback aria-hidden>{iniciales(usuario.nombre)}</AvatarFallback>
          </Avatar>
          <div className={cn("grid min-w-0 flex-1 gap-1", colapsado && "sr-only")}>
            <span className="truncate text-sm font-medium leading-none">{usuario.nombre}</span>
            <span className="truncate text-xs text-muted-foreground">{usuario.correo}</span>
            <Badge variant="secondary" className="mt-0.5">
              <span className="sr-only">Rol: </span>
              {rol}
            </Badge>
          </div>
        </div>
        <form action={cerrarSesion}>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton type="submit" tooltip="Cerrar sesión">
                <LogOut aria-hidden />
                <span>Cerrar sesión</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </form>
      </SidebarFooter>
    </Sidebar>
  );
}

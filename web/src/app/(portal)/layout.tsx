import { cookies } from "next/headers";

import { AppSidebar } from "@/components/app-sidebar";
import { Proveedores } from "@/components/proveedores";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { exigirUsuario } from "@/lib/dal";

export default async function LayoutPortal({ children }: LayoutProps<"/">) {
  const usuario = await exigirUsuario();
  const sidebarAbierto = (await cookies()).get("sidebar_state")?.value !== "false";

  return (
    <Proveedores>
      <a
        href="#contenido"
        className="sr-only z-50 rounded-md bg-primary px-3 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Saltar al contenido
      </a>
      <SidebarProvider defaultOpen={sidebarAbierto}>
        <AppSidebar
          usuario={{
            nombre: usuario.nombre,
            correo: usuario.correo,
            roles: usuario.roles,
            permisos: usuario.permisos,
          }}
        />
        <SidebarInset id="contenido" tabIndex={-1} className="outline-none">
          {children}
        </SidebarInset>
      </SidebarProvider>
    </Proveedores>
  );
}

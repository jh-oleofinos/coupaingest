import { LayoutDashboard, type LucideIcon } from "lucide-react";

import { PERMISOS, type Permiso } from "@/lib/permisos";

/*
  Menú del portal. Cada opción declara el permiso que requiere: el sidebar solo muestra
  lo que el usuario puede abrir. Para agregar un módulo nuevo basta con sumarlo aquí.
*/
export type OpcionMenu = { titulo: string; href: string; icono: LucideIcon; permiso: Permiso };
export type Modulo = { titulo: string; opciones: OpcionMenu[] };

export const MODULOS: Modulo[] = [
  {
    titulo: "Commodities",
    opciones: [
      {
        titulo: "Tablero",
        href: "/commodities",
        icono: LayoutDashboard,
        permiso: PERMISOS.commoditiesVer,
      },
    ],
  },
];

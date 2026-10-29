import type { Metadata } from "next";

import { TableroCommodities } from "@/components/commodities/tablero";
import { EncabezadoPagina } from "@/components/encabezado-pagina";
import { EstadoCarga } from "@/components/commodities/estado-carga";
import { exigirUsuario } from "@/lib/dal";
import { PERMISOS } from "@/lib/permisos";

export const metadata: Metadata = { title: "Commodities" };

export default async function PaginaCommodities() {
  await exigirUsuario(PERMISOS.commoditiesVer);
  return (
    <>
      <EncabezadoPagina
        titulo="Commodities"
        descripcion="Precios de referencia y su evolución"
        acciones={<EstadoCarga />}
      />
      <TableroCommodities />
    </>
  );
}

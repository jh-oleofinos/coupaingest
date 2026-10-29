import { reenviar } from "@/lib/bff";
import { PERMISOS } from "@/lib/permisos";

export async function GET() {
  return reenviar("/commodities/resumen", PERMISOS.commoditiesVer);
}

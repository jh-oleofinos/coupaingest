/*
  Permisos conocidos por la web. Deben existir en api/app/security/catalogo.py.
  La web los usa para mostrar u ocultar opciones; quien decide de verdad es la API.
*/
export const PERMISOS = {
  commoditiesVer: "commodities.ver",
  usuariosAdministrar: "usuarios.administrar",
} as const;

export type Permiso = (typeof PERMISOS)[keyof typeof PERMISOS];

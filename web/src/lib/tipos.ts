/* Contratos de la API (espejo de api/app/schemas.py). */

export type Rol = { codigo: string; nombre: string };

export type Perfil = {
  id: number;
  correo: string;
  nombre: string;
  roles: Rol[];
  permisos: string[];
  version_sesion: number;
};

export type PuntoSerie = { fecha: string; valor: string };

export type ResumenCommodity = {
  codigo: string;
  nombre: string;
  unidad: string;
  ultimo: PuntoSerie | null;
  anterior: PuntoSerie | null;
  variacion: string | null;
  variacion_pct: string | null;
};

export type Serie = {
  codigo: string;
  nombre: string;
  unidad: string;
  puntos: PuntoSerie[];
};

export type Corrida = { estado: string; inicio: string; fin: string | null };

export type EstadoCarga = { ultima: Corrida | null; ultima_exitosa: Corrida | null };

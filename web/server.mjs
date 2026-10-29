/*
  Servidor de producción del portal: HTTPS directo con Node, sin IIS.

  Variables (en el servidor vienen del Administrador de credenciales, ver docs/despliegue-windows.md):
    PORT                 puerto HTTPS (por defecto 443)
    HOST                 interfaz (por defecto 0.0.0.0)
    TLS_PFX_PATH         ruta al certificado .pfx emitido por la CA interna
    TLS_PFX_PASSPHRASE   contraseña del .pfx (secreto)

  Uso:  npm run build  →  NODE_ENV=production node server.mjs
*/
import { readFileSync } from "node:fs";
import { createServer } from "node:https";

import next from "next";

const puerto = Number.parseInt(process.env.PORT ?? "443", 10);
const host = process.env.HOST ?? "0.0.0.0";
const pfx = process.env.TLS_PFX_PATH;
if (!pfx) {
  console.error("Falta TLS_PFX_PATH: el portal solo se publica con HTTPS.");
  process.exit(1);
}

const app = next({ dev: false });
const manejar = app.getRequestHandler();

await app.prepare();

createServer(
  {
    pfx: readFileSync(pfx),
    passphrase: process.env.TLS_PFX_PASSPHRASE,
    minVersion: "TLSv1.2",
  },
  (req, res) => manejar(req, res),
).listen(puerto, host, () => {
  console.log(`Portal Oleofinos escuchando en https://${host}:${puerto}`);
});

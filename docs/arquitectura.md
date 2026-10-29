# Arquitectura y seguridad

## Piezas

| Pieza | Tecnología | Escucha en | Responsabilidad |
|---|---|---|---|
| Web | Next.js 16 (App Router), Auth.js v5 | HTTPS 443 | Login, sesión, páginas, BFF (`/api/*`) |
| API | FastAPI, SQLAlchemy | 127.0.0.1:8000 | Credenciales, roles/permisos, datos, bitácora |
| Base | SQL Server Express (una base por proyecto) | local | Esquemas `app` (seguridad), `dat` (datos), `ctl` (cargas) |

El navegador **nunca** habla con la API. Todo pasa por el servidor de Next.js.

## Flujo de una petición

1. **Proxy** (`web/src/proxy.ts`): pone la CSP con nonce y redirige a `/login` si no hay cookie.
   Es solo una redirección optimista; no es el control de acceso.
2. **Capa de acceso** (`web/src/lib/dal.ts`): en cada página y en cada `/api/*` lee la sesión y pide
   el perfil a la API. Sin perfil → `/login`; sin permiso → `/sin-acceso` o 403.
3. **Token hacia la API** (`web/src/lib/api.ts`): JWT HS256 de 60 s firmado con `API_TOKEN_SECRET`,
   con el id del usuario y su *versión de sesión*.
4. **API** (`api/app/security/deps.py`): valida firma, emisor, audiencia y vigencia. Vuelve a leer al
   usuario de la base, revisa que esté activo y que la versión de sesión coincida, y valida el permiso.

## Decisiones de seguridad

| Tema | Cómo se resolvió |
|---|---|
| Contraseñas | Argon2id. Mínimo 12 caracteres. Rehash automático si cambian los parámetros |
| Fuerza bruta | 5 intentos fallidos → bloqueo de 15 min. El contador se incrementa de forma atómica en la base (probado con 20 intentos en paralelo) |
| Enumeración | Mismo mensaje para todo fallo; hash señuelo para que un correo inexistente tarde lo mismo |
| Sesión | Cookie HttpOnly, Secure (`__Secure-`), SameSite=Lax. 8 h de inactividad y 8 h máximo desde el login |
| Cerrar sesión | Sube la versión de sesión en la base: cualquier copia de la cookie deja de servir en todos los equipos |
| Bajas y cambios de rol | Se aplican en la siguiente petición (el perfil se pide a la API en cada página) |
| Autorización | Por permisos (`commodities.ver`, `usuarios.administrar`), validados en Next.js **y** en la API |
| Entra ID (cuando se active) | Issuer de nuestro tenant (no `/common`), se verifica `tid` y se vincula por `oid` inmutable |
| Datos de cargas fallidas | El tablero solo usa precios de corridas exitosas |
| CSP | `script-src` con nonce por petición y `strict-dynamic`; `frame-ancestors 'none'`; `form-action` limitado |
| Cabeceras | HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`; sin `X-Powered-By` |
| Caché | Respuestas `/api/*` con `Cache-Control: no-store` |
| Redirecciones | Solo rutas internas después del login |
| Errores | La API y el BFF nunca devuelven detalles internos; van al log del servidor |
| Secretos | Administrador de credenciales de Windows (keyring) de cada cuenta de servicio; nada en archivos |
| Base de datos | Usuarios por función: la API no puede borrar ni modificar la bitácora; el job no toca `app` |
| Auditoría | `app.bitacora_acceso`: login ok/fallido/bloqueado/rechazado, logout, acceso denegado |

## Decisiones de diseño

- **Sin `cacheComponents`** en Next.js: todas las páginas dependen de la sesión y se generan por
  petición; además el nonce de la CSP lo requiere.
- **HTTPS directo con `server.mjs`** (sin IIS). Next.js no usa `output: standalone` porque es
  incompatible con un servidor propio.
- **Precios solo se agregan**: una corrección de la fuente es una versión nueva (`fecha_carga`); el
  tablero muestra la más reciente de una corrida exitosa.
- **Logo y colores provisionales**: los tokens están en `web/src/app/globals.css` y el logo en
  `web/src/components/logo.tsx`.

## Al integrarse a Oleonet

- La identidad cambia a Entra ID (el proveedor ya está en `web/src/auth.ts`); la tabla de roles se conserva.
- Las rutas, componentes y el BFF se mueven como están; la API puede quedarse como servicio propio o
  pasar al backend de Oleonet (decisión pendiente en la sesión de Oleonet).

## Pruebas y verificación hechas

- API: 20 pruebas (`uv run pytest`): login, enumeración, bloqueo, tokens inválidos o vencidos,
  `alg=none`, permisos por rol, revocación de sesión, Entra por `oid`, cargas fallidas.
- Web: `tsc`, ESLint y `next build` sin errores.
- Navegador (Playwright, HTTPS): login, error de credenciales, tablero, cambio de commodity y rango,
  sidebar colapsado, móvil, logout, cookie copiada rechazada tras logout, rol lector.
- Accesibilidad: axe-core sin violaciones WCAG 2.1 AA en login y tablero; navegación con teclado;
  sin scroll horizontal al 200 % de zoom; contrastes ≥ 4.5:1 en texto y ≥ 3:1 en controles.

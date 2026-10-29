# Portal Oleofinos (oleoweb)

Portal interno con login, roles y un primer módulo: **tablero de Commodities**. Se construye con el
stack del sitio de Oleonet (Next.js App Router, TypeScript, Tailwind + shadcn/ui, TanStack Table y
Query, Zustand, React Hook Form + Zod, Auth.js) para integrarse a Oleonet cuando esté publicado.
Mientras tanto corre en el Windows Server, con SQL Server Express y sin IIS.

```
Navegador ──HTTPS──▶ web/ (Next.js, server.mjs)          ──127.0.0.1──▶ api/ (FastAPI) ──▶ SQL Server
                     · login y sesión (Auth.js)                          · valida token, versión
                     · revisa sesión y permiso en cada página               de sesión y permiso
                     · /api/* = BFF hacia la API                         · bitácora de accesos
Programador de tareas ──diario──▶ job de ingesta (pendiente) ──▶ dat.precio / ctl.corrida
```

| Carpeta | Qué hay |
|---|---|
| `web/` | Next.js: login, sidebar, tablero, BFF (`src/app/api`), proxy con CSP |
| `api/` | FastAPI: auth, roles y permisos, commodities, CLI de administración, pruebas |
| `db/sqlserver/` | Scripts versionados (V001…V004) para crear la base en SQL Server |
| `ops/windows/` | Arranque de los servicios (WinSW + PowerShell) |
| `docs/` | Arquitectura y seguridad, despliegue en Windows |

## Desarrollo local

Requisitos: Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 24.

```bash
# API (SQLite en desarrollo)
cd api
cp .env.example .env                 # completa API_TOKEN_SECRET
uv sync
uv run python -m app.cli crear-tablas
uv run python -m app.cli sembrar-roles
uv run python -m app.cli datos-ejemplo          # series INVENTADAS, solo para la interfaz
uv run python -m app.cli crear-usuario --correo tu@oleofinos.com.mx --nombre "Tu Nombre" --rol administrador
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
uv run pytest

# Web (otra terminal)
cd web
cp .env.example .env.local           # mismo API_TOKEN_SECRET que la API
npm ci
npm run dev                          # http://localhost:3000
```

## Roles

Hoy: **Administrador** (todo) y **Lector** (tablero). El código revisa *permisos*, no nombres de rol.
Para agregar un rol: declararlo en `api/app/security/catalogo.py` y en un script `db/sqlserver/V00N`.
Para agregar un módulo: sumarlo a `web/src/lib/navegacion.ts` con el permiso que requiere.

## Pendiente

- Logo oficial: reemplazar `web/src/components/logo.tsx` (instrucciones en el archivo).
- Job de ingesta: adaptar el script actual de commodities para escribir en `dat.precio` y `ctl.corrida`.
- Pantalla de administración de usuarios (hoy se administra con `python -m app.cli`).
- Entra ID: el código está listo; falta el registro de la aplicación en el tenant.

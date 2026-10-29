# coupa-ingest

Proceso mensual que toma un Excel de SharePoint, convierte cada pestaña a CSV sin tocar valores y lo envía a Coupa por API. Corre en un Windows Server con el Programador de tareas.

```
SharePoint (Graph) ──► data/runs/<run_id>/source.xlsx ──► csv/<tabla>.csv ──► API de Coupa
                                                   └──► manifest.json (cifra de control)
```

## Estructura

| Ruta | Qué hace |
| --- | --- |
| `src/coupa_ingest/cli.py` | Comandos `run`, `secrets set`, `check` |
| `src/coupa_ingest/pipeline.py` | Orquesta una corrida |
| `src/coupa_ingest/sharepoint.py` | Descarga el Excel con Microsoft Graph |
| `src/coupa_ingest/transform.py` | Excel → CSV por pestaña; valida llaves y encabezados |
| `src/coupa_ingest/coupa_client.py` | Sesión de importación, lotes PUT, estado, resumen y errores |
| `src/coupa_ingest/control.py` | Manifiesto por corrida (filas en archivo / enviadas / aceptadas) |
| `src/coupa_ingest/secrets.py` | Secretos en el Administrador de credenciales de Windows |
| `config/settings.example.toml` | Plantilla de configuración (sin secretos) |
| `scripts/run_monthly.ps1` | Envoltorio que llama el Programador de tareas |
| `scripts/register_task.ps1` | Registra la tarea mensual |
| `tests/` | Pruebas con datos sintéticos |

## Reglas que sigue

- **Sin secretos en archivos.** El client secret de Graph y la API key de Coupa se capturan en consola y viven en el Administrador de credenciales, por ambiente.
- **Valores tal cual.** Todo se lee como texto: no se pierden ceros a la izquierda ni se reinterpretan fechas o decimales.
- **Todo o nada al validar.** Si una pestaña no existe, tiene columnas sin encabezado o llaves vacías o duplicadas, no se envía nada.
- **Rastro por corrida.** `data/runs/<run_id>/` guarda el Excel leído, los CSV enviados, el manifiesto y el resumen y los errores de Coupa. `logs/<run_id>.log` lleva `run_id` en cada línea. `data/` y `logs/` contienen datos de la empresa y no se versionan.
- **Una corrida a la vez.** Un candado en `data\.lock` impide que la tarea programada y una corrida manual se encimen.
- **Pestañas ocultas y vacías.** Las ocultas no se envían; una pestaña sin filas detiene la corrida. Ambas cosas se cambian en la configuración.
- **Archivo sin cambios.** Se compara con la última corrida exitosa (`data\state.json`); `if_unchanged` decide si se envía, se omite o se marca error.
- **Reintentos seguros.** Las consultas a Coupa se reintentan solas; un envío (PUT/POST) solo se repite si Coupa respondió 429, para no duplicar lotes.
- **Limpieza.** `data\runs\` y `logs\` se borran después de `retention_days` (90 por defecto).
- **Configuración incompleta.** `run` y `check` se detienen si quedan valores de ejemplo (`PENDIENTE`, ids en ceros).
- **Código de salida.** 0 = correcto, 1 = falla de la corrida, 2 = configuración o secretos.

## Instalación (Windows Server)

```powershell
cd C:\proyectos\coupa
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e .[dev]
copy config\settings.example.toml config\settings.toml   # y editarlo
```

Iniciar sesión **con la cuenta de servicio** que correrá la tarea, porque las credenciales de Windows son por usuario:

```powershell
.venv\Scripts\python -m coupa_ingest secrets set graph_client_secret
.venv\Scripts\python -m coupa_ingest secrets set coupa_api_key
.venv\Scripts\python -m coupa_ingest check
```

## Uso

El proceso descarga el archivo de SharePoint por sí solo en cada corrida; no hay paso manual.

```powershell
# Revisa configuración, secretos y acceso real al archivo (no lo descarga)
.venv\Scripts\python -m coupa_ingest check --conexion

# Descarga de SharePoint y genera los CSV, sin enviar a Coupa
.venv\Scripts\python -m coupa_ingest run --dry-run

# Corrida completa (o solo una pestaña)
.venv\Scripts\python -m coupa_ingest run
.venv\Scripts\python -m coupa_ingest run --sheet VW_YVA05

# Solo para pruebas de desarrollo: usar un .xlsx local en lugar de SharePoint
.venv\Scripts\python -m coupa_ingest run --dry-run --file C:\ruta\prueba.xlsx
```

La configuración se toma de `config\settings.toml`; otra ruta se indica con `--config` o con la variable de entorno `COUPA_INGEST_CONFIG`.

## Calendarización

```powershell
# PowerShell como administrador; pide la contraseña de la cuenta de servicio
.\scripts\register_task.ps1 -ServiceAccount "DOMINIO\svc_coupa" -Day 1 -Time "06:00"
schtasks /Run /TN "Oleofinos\CoupaIngestMensual"   # prueba manual
```

## Pruebas

```powershell
.venv\Scripts\python -m pytest
```

## Pendientes

- [ ] Coupa: rutas exactas de la API, encabezado de autenticación, formato del cuerpo (¿CSV?), límite de filas por PUT, formato del resumen y ambiente de pruebas. Ajustar `ENDPOINTS`, el encabezado en `CoupaClient` y `_apply_summary`.
- [ ] TI: registro de aplicación en Entra ID con `Sites.Selected`, autorizado sobre el OneDrive donde vive el archivo (`oleofinos1-my.sharepoint.com/personal/simon_dorado_oleofinos_com_mx`).
- [ ] Carpeta y nombre exacto del archivo (`file_path`).
- [ ] Mover el archivo a un sitio de SharePoint del equipo: en un OneDrive personal depende de la cuenta de una persona.
- [ ] Tablas destino en Coupa y columnas llave por pestaña (hoy: todas las pestañas, tabla = nombre de la pestaña).
- [ ] Cuenta de servicio en el Windows Server y versión de Python instalada.
- [ ] Aviso por correo o Teams cuando la corrida falle.
- [ ] Qué hacer si Coupa rechaza filas: todo o nada, o envío parcial.

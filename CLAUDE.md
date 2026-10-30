# Contexto para Claude: coupaingest ([PROY] Envío a Coupa)

Última actualización: 2026-10-29 · Dueño: Jorge Herrera (Inteligencia de Negocios, Oleofinos)

## Qué es

Proceso Python que corre **una vez al mes** en un Windows Server (Programador de tareas). En cada corrida:

1. Descarga por sí solo, con Microsoft Graph, un Excel del OneDrive de Simón Dorado. No hay pasos manuales.
2. Convierte **cada pestaña** a un CSV sin tocar valores; todo se lee como texto.
3. Envía cada CSV a Coupa por API, con la API key de un usuario que dará Coupa.
4. Guarda una copia de lo leído y lo enviado, y la cifra de control.

Es la solución **provisional**. La definitiva vivirá en la plataforma Azure (Data Factory + Container Apps), por eso la lógica está en módulos portables y no en el script de Windows.

## Reglas de trabajo (vienen del "Mapa de sesiones Oleofinos")

- Explicar el diseño antes de construir; no construir nada sin acuerdo con Jorge.
- Nunca marcar algo como decidido sin confirmación explícita de Jorge. Estados: Propuesta → En discusión → Decidido; "Hecho" = dato verificado.
- Secretos: en `.env` (fuera de git) o en el Administrador de credenciales; nunca en el código versionado. Jorge aceptó `.env` para avanzar rápido (2026-10-29). No mostrar su contenido en el chat.
- No pegar datos de negocio de SAP en el chat: solo nombres de vistas, columnas, conteos, agregados y errores. QAS se trata como producción.
- Los datos personales (nombres, RFC, direcciones, placas) se declaran como sensibles.
- Responder en español, conciso, solo lo que se pregunta. No inflar estimaciones. Ningún costo parcial se llama "total".
- Trabajar solo en este proyecto. Lo de otras sesiones se anota en su sección del mapa.
- Si una regla de esta lista choca con lo que pida Jorge, preguntarle.

Mapa de sesiones (secciones "Reglas que aplican a todas las sesiones", "[PANORAMA]" y "[PROY] Envío a Coupa"): https://claude.ai/artifact/Eqhdd8g8ewomt3EgE977iB
Arquitectura de datos en Confluence: https://oleofinos.atlassian.net/wiki/spaces/~7120206d5b9ec4262843c18659523be1f54fa9/pages/39092225/Arquitectura+de+datos+Oleofinos

## Hechos

- Coupa pidió los datos "tal como vienen" (raw), sin transformar. Oleofinos orquesta el envío.
- Flujo de la API, según el documento de ejemplo de llama.ai (LLamasoft, hoy Coupa): crear el modelo una vez, abrir una sesión de importación, enviar lotes por PUT (responde 202, asíncrono), revisar el estado de cada lote, cerrar la sesión y consultar resumen y errores.
- Acceso: Coupa dará un usuario del que se obtiene la API key. Jorge dice que ya la tiene guardada.
- Origen: el Excel está en el OneDrive personal de Simón Dorado: `oleofinos1-my.sharepoint.com/personal/simon_dorado_oleofinos_com_mx`. Las pestañas tienen nombres de vista SAP (p. ej. `VW_YVA05`); algunas pasan de 40,000 filas.
- Repositorio: `C:\proyectos\coupaingest` → GitHub `jh-oleofinos/coupaingest`, rama `main`. El portal oleoweb (commodities) se subió ahí por error y se retiró; sigue en la historia, en el commit "Primer push". Su ubicación es `C:\proyectos\oleoweb`.

## Decisiones

| Punto | Estado |
| --- | --- |
| ~~Origen: Excel en el OneDrive de Simón~~ → **Origen: las vistas de SAP Datasphere directamente** (espacio/esquema `OLEOFINOS`), las mismas que alimentan el Excel `Para_Ventas.xlsx` | **Decidido** (2026-10-30); reemplaza la lectura de SharePoint |
| Ejecución mensual con el Programador de tareas de Windows | Decidido (lo pidió Jorge) |
| Se procesan todas las pestañas; cada una a su CSV; tabla destino = nombre de la pestaña salvo override | Propuesta implementada |
| Cada pestaña se envía completa, tal como está: sin exclusiones, sin columnas llave, tabla destino = nombre de la pestaña | **Decidido** (2026-10-29) |
| Lectura de SharePoint con Graph e inicio de sesión de usuario una vez (`login`, token renovado solo), **con la cuenta de Jorge, como solución provisional**; app de Entra ID con `Sites.Selected` o cuenta de servicio queda como opción definitiva | **Decidido** (2026-10-30) |
| `if_unchanged` (qué hacer si el archivo no cambió desde el último envío): hoy `send` | **Abierta**: Jorge decide entre send, skip y fail |
| Si Coupa rechaza filas: todo o nada, o envío parcial | Abierta |
| Formato del cuerpo: JSON (lo exige la API de llama.ai) | **Decidido** (2026-10-29) |

## Hallazgos del Excel `Para_Ventas.xlsx` (2026-10-30)

- 11 tablas por Power Query → ODBC `dsn=DATASPHERE_OLEOFINOS`, esquema `OLEOFINOS`, `SELECT *` por vista, sin filtros ni transformaciones. El DSN está en el equipo de Simón, no en el de Jorge.
- Vistas y filas: vw_YFACTURAS_IMASA 190,371 · vw_FACTURASV2 76,498 · vw_YFACTURAS_FRESNO_GLOBAL 46,293 · vw_YVA05 45,108 · vw_MARM 5,016 · vw_MARA 4,095 · vw_Inventarios 3,747 · vw_Remisiones 301 · vw_MB58 237 · vw_CXC 122 (≈371,800). Hoja1–4 vacías.
- Pendiente: confirmar en Datasphere si las vistas son federadas (leen S/4 en vivo) o replicadas/persistidas.

## Estado del código

31 pruebas pasando con datos sintéticos (`pytest`). No se ha probado contra Datasphere, SharePoint ni Coupa reales.

| Archivo | Qué hace | Estado |
| --- | --- | --- |
| `src/coupa_ingest/cli.py` | `run`, `secrets set`, `check [--conexion]`. Salida: 0 ok, 1 falla, 2 configuración | Listo |
| `src/coupa_ingest/config.py` | Configuración con pydantic; detecta valores de ejemplo (`PENDIENTE`, ids en ceros); ruta por `--config` o `COUPA_INGEST_CONFIG` | Listo |
| `src/coupa_ingest/datasphere.py` | **Origen por defecto** (`source = "datasphere"`). `hdbcli` (sin ODBC), usuario de BD del espacio, contraseña `DATASPHERE_PASSWORD` en `.env`. COUNT(*) + `SELECT *` por bloques → CSV todo texto (decimales exactos, fechas ISO, nulos ""); se detiene si COUNT ≠ leídas. `check --conexion` valida conexión, vistas visibles y filas | Listo; **sin probar contra Datasphere** (falta el usuario de BD) |
| `src/coupa_ingest/sharepoint.py` | Graph. `auth = "usuario"` (por defecto): `coupa-ingest login` una vez con cuenta M365, token cifrado DPAPI en `data/.msal_token.bin`, se renueva solo. `auth = "app"`: Sites.Selected + secreto (TI). Ubica el archivo por `file_url` (API /shares) | **Sin probar contra Microsoft** |
| `src/coupa_ingest/transform.py` | Excel → CSV; abre el libro una vez; omite pestañas ocultas; valida encabezados, llaves y pestañas vacías; parte en lotes | Listo |
| `src/coupa_ingest/coupa_client.py` | Import Session API de llama.ai según el PDF de Coupa: `X-API-Key`, `/v4/import/session`, lotes JSON (todo texto, vacío = ""), sondeo del `Location`, cierre, resumen, status y errores paginados. PUT/POST se reintentan solo ante 429/503 | Rutas y auth según PDF; **supuestos**: campo del sessionId, nombres de totales del resumen, forma de las páginas |
| `src/coupa_ingest/batching.py` | Lotes por filas (`batch_rows`) y por tamaño (`max_batch_mb`, 10 MB supuesto); ante 413 parte el lote a la mitad, reenvía y baja el límite para el resto de la corrida | Listo; sin probar contra Coupa |
| `src/coupa_ingest/pipeline.py` | Orquesta; candado `data/.lock`; `state.json` con el eTag del último éxito; retención de 90 días | Listo |
| `src/coupa_ingest/control.py` | `manifest.json` por corrida (archivo = enviadas = exitosas y 0 errores) y `data/registro_lotes.csv` acumulado por lote | Listo |
| `src/coupa_ingest/secrets.py` | Variable de entorno → `.env` → Administrador de credenciales | Listo |
| `scripts/run_monthly.ps1`, `scripts/register_task.ps1` | Envoltorio y registro de la tarea (`schtasks /SC MONTHLY`, contraseña pedida en consola) | Listo; sin probar en el servidor |
| `config/settings.example.toml` | Plantilla de configuración | Faltan valores reales |

### API de Coupa (llama.ai)

Fuente: "LLAPI Ingest Examples.pdf" y https://developer.llama.ai (requiere sesión). Es llama.ai (Supply Chain Design), no Coupa Core. Falta de Coupa: `model_id` (no hay que crear modelo; `coupa-ingest modelos` lista los visibles), confirmar host `https://api.llama.ai`, límite por PUT y ejemplo de respuestas. La primera corrida real dirá si los supuestos de respuesta son correctos (`data/runs/<run_id>/coupa_*.json`).

**Incidente 2026-10-29:** la API key anterior quedó en `secrets.py` en el commit `ea8e692` (subido a GitHub). Jorge generó una nueva; falta confirmar que Coupa revocó la anterior.

## Pendientes

1. Administrador de Datasphere: usuario de BD de solo lectura en `OLEOFINOS` (p. ej. `OLEOFINOS#COUPA`), IPs (equipo de Jorge y servidor) en IP Allowlist, y las 10 vistas expuestas para consumo. Jorge no tiene rol de administrador. (El `login` de Microsoft quedó bloqueado por consentimiento de administrador; ya no se necesita.)
2. TI (servidor): Python 3.11+, cuenta de servicio, carpeta, salida 443 a Datasphere/api.llama.ai/pypi, IP pública de salida, registro de la tarea.
3. Coupa: `model_id`, límite por PUT y ejemplos de respuesta. Primera prueba: `run --file <excel> --sheet <pestaña chica>`.
4. ~~Por pestaña: tabla destino, llaves y exclusiones~~ → Decidido: todo tal como está. Falta confirmar si las pestañas ocultas también van.
5. Los 19 bytes extra eran la API key (ver incidente). Borrar `C:\proyectos\coupa`.
6. Windows Server: Python 3.11+, cuenta de servicio, `pip install -e .`, cargar secretos **con la cuenta de servicio**, `register_task.ps1`.
7. Aviso por correo o Teams cuando una corrida falle.
8. Decisiones abiertas: `if_unchanged` y qué hacer ante filas rechazadas.

## Comandos

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e .[dev]
copy config\settings.example.toml config\settings.toml
.venv\Scripts\python -m coupa_ingest secrets set graph_client_secret
.venv\Scripts\python -m coupa_ingest secrets set coupa_api_key
.venv\Scripts\python -m coupa_ingest check --conexion
.venv\Scripts\python -m coupa_ingest run --dry-run
.venv\Scripts\python -m pytest
.venv\Scripts\ruff check src tests
```

`config/settings.toml`, `data/` y `logs/` están en `.gitignore`: contienen configuración local y datos de la empresa.

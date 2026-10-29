# Despliegue en el Windows Server

Ruta de instalación usada en los scripts: `C:\oleoweb` (el repositorio clonado).

## 1. Programas

| Programa | Para qué |
|---|---|
| Python 3.12 x64 + [uv](https://docs.astral.sh/uv/) | API |
| Node.js 24 LTS | Web |
| Git for Windows | Desplegar desde el repo |
| Microsoft ODBC Driver 18 for SQL Server | Conexión de la API a SQL Server |
| [WinSW](https://github.com/winsw/winsw) (x64) | API y web como servicios de Windows |
| Certificado `.pfx` de la CA interna | HTTPS del portal |

## 2. Cuentas de servicio

Dos cuentas de dominio sin privilegios, con permiso "Iniciar sesión como servicio":
`DOMINIO\svc_oleoweb_api` y `DOMINIO\svc_oleoweb_web`.
Permisos de carpeta: lectura sobre `C:\oleoweb`, escritura solo sobre `C:\oleoweb\logs`. El `.pfx`
solo lo puede leer `svc_oleoweb_web`.

## 3. Base de datos

```powershell
sqlcmd -S OLF05ZGTWB01\SQLEXPRESS -E -Q "CREATE DATABASE commodities"
sqlcmd -S OLF05ZGTWB01\SQLEXPRESS -E -Q "CREATE LOGIN [DOMINIO\svc_oleoweb_api] FROM WINDOWS"
cd C:\oleoweb\db\sqlserver
foreach ($s in Get-ChildItem V*.sql | Sort-Object Name) {
  sqlcmd -S OLF05ZGTWB01\SQLEXPRESS -E -d commodities -b -i $s.FullName
}
```

Antes de V004, reemplaza `DOMINIO\svc_...` por las cuentas reales. El login del job se crea cuando
exista el job de ingesta.

## 4. Secretos (Administrador de credenciales)

Cada secreto se guarda en el Administrador de credenciales **de la cuenta de servicio que lo usa**.
Abre una consola como esa cuenta y captúralo (el valor se escribe sin que se vea):

```powershell
runas /user:DOMINIO\svc_oleoweb_api powershell
cd C:\oleoweb\api
.venv\Scripts\python -m keyring set oleoweb DATABASE_URL
.venv\Scripts\python -m keyring set oleoweb API_TOKEN_SECRET
```

```powershell
runas /user:DOMINIO\svc_oleoweb_web powershell
cd C:\oleoweb\api
.venv\Scripts\python -m keyring set oleoweb API_TOKEN_SECRET   # el MISMO valor que el de la API
.venv\Scripts\python -m keyring set oleoweb AUTH_SECRET
.venv\Scripts\python -m keyring set oleoweb TLS_PFX_PASSPHRASE
```

- `DATABASE_URL`:
  `mssql+pyodbc://@OLF05ZGTWB01\SQLEXPRESS/commodities?driver=ODBC+Driver+18+for+SQL+Server&Trusted_Connection=yes&Encrypt=yes`
- Para generar `API_TOKEN_SECRET` y `AUTH_SECRET` usa:
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`

## 5. Instalar y compilar

```powershell
cd C:\oleoweb\api;  uv sync --no-dev
cd C:\oleoweb\web;  npm ci;  npm run build
```

Ajusta `AUTH_URL` y `TLS_PFX_PATH` en `ops\windows\iniciar-web.ps1`.

## 6. Servicios

```powershell
cd C:\oleoweb\ops\windows
# Copia WinSW-x64.exe dos veces: oleoweb-api.exe y oleoweb-web.exe (junto a sus .xml)
.\oleoweb-api.exe install /p     # pide la contraseña de la cuenta de servicio
.\oleoweb-web.exe install /p
.\oleoweb-api.exe start
.\oleoweb-web.exe start
```

Firewall: abre el 443 **solo para la red interna**. El 8000 no se abre: la API solo escucha en
127.0.0.1.

```powershell
New-NetFirewallRule -DisplayName "Portal Oleofinos HTTPS" -Direction Inbound -Protocol TCP `
  -LocalPort 443 -RemoteAddress LocalSubnet -Action Allow
```

## 7. Primer administrador

Corre el CLI con **tu** cuenta de Windows (con permisos sobre la base), no con la de la API:

```powershell
cd C:\oleoweb\api
$env:ENTORNO="prd"
$env:DATABASE_URL="mssql+pyodbc://@OLF05ZGTWB01\SQLEXPRESS/commodities?driver=ODBC+Driver+18+for+SQL+Server&Trusted_Connection=yes&Encrypt=yes"
$env:API_TOKEN_SECRET="(cualquier valor de 32+ caracteres; el CLI no lo usa)"
.venv\Scripts\python -m app.cli crear-usuario --correo jorge.herrera@oleofinos.com.mx --nombre "Jorge Herrera" --rol administrador
```

## 8. Verificación

- `https://<servidor>/` redirige a `/login`; `http://<servidor>:8000` no responde desde otro equipo.
- La cookie se llama `__Secure-authjs.session-token` y es HttpOnly.
- Después de cerrar sesión, recargar el tablero lleva a `/login`.
- `app.bitacora_acceso` registra el login y el logout.

## 9. Respaldos

SQL Express no tiene Agent: crea una tarea diaria en el Programador de tareas con
`sqlcmd -Q "BACKUP DATABASE commodities TO DISK='...' WITH CHECKSUM"` y copia el
archivo fuera del servidor. Haz una restauración de prueba periódicamente.

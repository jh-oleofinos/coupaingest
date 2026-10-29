# Arranca la API (FastAPI) solo en localhost. La corre WinSW como servicio "oleoweb-api".
# Los secretos (DATABASE_URL, API_TOKEN_SECRET) los lee la propia API del Administrador de
# credenciales de la cuenta de servicio (keyring, servicio "oleoweb").
$ErrorActionPreference = "Stop"
$raiz = "C:\oleoweb"
Set-Location "$raiz\api"
$env:ENTORNO = "prd"
& "$raiz\api\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-server-header

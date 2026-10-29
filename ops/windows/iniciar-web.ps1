# Arranca el portal (Next.js con HTTPS). La corre WinSW como servicio "oleoweb-web".
# Lee los secretos del Administrador de credenciales de la cuenta de servicio y los pasa
# como variables de entorno SOLO a este proceso. Nunca se escriben en disco.
$ErrorActionPreference = "Stop"
$raiz = "C:\oleoweb"
$py = "$raiz\api\.venv\Scripts\python.exe"

function Leer-Secreto([string]$nombre) {
    $valor = & $py -c "import keyring,sys; v=keyring.get_password('oleoweb', sys.argv[1]); print(v or '')" $nombre
    if (-not $valor) { throw "Falta el secreto '$nombre' en el Administrador de credenciales." }
    return $valor
}

$env:NODE_ENV = "production"
$env:PORT = "443"
$env:API_URL = "http://127.0.0.1:8000"
$env:AUTH_URL = "https://portal.oleofinos.local"       # <- nombre real del servidor
$env:TLS_PFX_PATH = "C:\oleoweb\certificados\portal.pfx" # <- certificado de la CA interna
$env:AUTH_SECRET = Leer-Secreto "AUTH_SECRET"
$env:API_TOKEN_SECRET = Leer-Secreto "API_TOKEN_SECRET"
$env:TLS_PFX_PASSPHRASE = Leer-Secreto "TLS_PFX_PASSPHRASE"
# Entra ID (opcional): descomentar cuando exista el registro de la aplicación.
# $env:AUTH_MICROSOFT_ENTRA_ID_ID = "<client id>"
# $env:AUTH_MICROSOFT_ENTRA_ID_ISSUER = "https://login.microsoftonline.com/<tenant id>/v2.0"
# $env:AUTH_MICROSOFT_ENTRA_ID_SECRET = Leer-Secreto "AUTH_MICROSOFT_ENTRA_ID_SECRET"

Set-Location "$raiz\web"
& node server.mjs

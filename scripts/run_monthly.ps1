# Envoltorio que ejecuta el Programador de tareas de Windows.
# Corre una corrida completa y devuelve el código de salida del proceso
# (0 = correcto, 1 = falla de la corrida, 2 = configuración).
# Uso manual:  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_monthly.ps1 [-DryRun]

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "No existe el entorno virtual en $Root\.venv. Ver README (Instalación)."
    exit 2
}

$PyArgs = @("-m", "coupa_ingest", "run")
if ($DryRun) { $PyArgs += "--dry-run" }

& $Python @PyArgs
$code = $LASTEXITCODE

# El historial de la tarea registra el código de salida. Aviso por correo/Teams: pendiente.
exit $code

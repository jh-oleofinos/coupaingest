# Registra la tarea mensual en el Programador de tareas de Windows.
# Ejecutar en PowerShell como administrador, en el Windows Server.
# La contraseña de la cuenta de servicio se pide en consola (no se guarda en el script).
#
# Ejemplo:
#   .\scripts\register_task.ps1 -ServiceAccount "OLEOFINOS\svc_coupa" -Day 1 -Time "06:00"

param(
    [Parameter(Mandatory = $true)][string]$ServiceAccount,
    [int]$Day = 1,
    [string]$Time = "06:00",
    [string]$TaskName = "Oleofinos\CoupaIngestMensual"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $Root "scripts\run_monthly.ps1"
$Action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Script`""

# /RP * hace que schtasks pida la contraseña de forma interactiva.
schtasks.exe /Create /F `
    /TN $TaskName `
    /TR $Action `
    /SC MONTHLY /D $Day /ST $Time `
    /RU $ServiceAccount /RP * `
    /RL LIMITED

Write-Host "Tarea '$TaskName' registrada: día $Day de cada mes a las $Time, como $ServiceAccount."
Write-Host "Prueba manual:  schtasks /Run /TN `"$TaskName`""

param()

$ErrorActionPreference = "Stop"
$backendDir = Join-Path $PSScriptRoot "..\dist_backend"
$backendExe = Join-Path $backendDir "USPEX_Runner_Backend.exe"

if (-not (Test-Path $backendDir)) {
  New-Item -ItemType Directory -Path $backendDir | Out-Null
}

if (-not (Test-Path $backendExe)) {
  # Minimal placeholder so tauri build script can match bundle resource in dev mode.
  [System.IO.File]::WriteAllBytes((Resolve-Path $backendDir | ForEach-Object { Join-Path $_ "USPEX_Runner_Backend.exe" }), [byte[]](0x4D,0x5A))
  Write-Host "Created dev placeholder: $backendExe"
}

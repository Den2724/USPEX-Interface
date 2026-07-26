param(
  [string]$PythonExe = "python",
  [string]$Version = "",
  [switch]$SkipNpmInstall,
  [switch]$SkipPipInstall
)

$ErrorActionPreference = "Stop"

# ─── Resolve project root (this script lives in packaging/) ───────────────────
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

# ─── 0. Patch version in tauri.conf.json if -Version supplied ─────────────────
if ($Version -ne "") {
  $confPath = Join-Path $Root "src-tauri\tauri.conf.json"
  $conf = Get-Content $confPath -Raw | ConvertFrom-Json
  $conf.package.version = $Version
  $utf8NoBOM = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllText($confPath, ($conf | ConvertTo-Json -Depth 10), $utf8NoBOM)
  Write-Host "[0/4] Version set to $Version"
}

# ─── 1. Python dependencies ───────────────────────────────────────────────────
if (-not $SkipPipInstall) {
  Write-Host "[1/4] Installing Python dependencies..."
  & $PythonExe -m pip install --upgrade pip
  & $PythonExe -m pip install -r requirements.txt
  & $PythonExe -m pip install pyinstaller
} else {
  Write-Host "[1/4] Skipping pip install (SkipPipInstall flag set)."
}

# ─── 2. Build Python backend ──────────────────────────────────────────────────
Write-Host "[2/4] Building backend (USPEX_Runner_Backend.exe)..."
if (Test-Path "build")         { Remove-Item "build"         -Recurse -Force }
if (Test-Path "dist_backend")  { Remove-Item "dist_backend"  -Recurse -Force }

& $PythonExe -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --name USPEX_Runner_Backend `
  --noconsole `
  --distpath dist_backend `
  --collect-all flask `
  --collect-all jinja2 `
  --collect-all werkzeug `
  --collect-all click `
  --collect-all itsdangerous `
  --add-data "webapp;webapp" `
  --add-data "app;app" `
  run_backend.py

if (-not (Test-Path "dist_backend\USPEX_Runner_Backend.exe")) {
  throw "Backend executable was not generated. Check PyInstaller output above."
}
Write-Host "  -> dist_backend\USPEX_Runner_Backend.exe OK"

# ─── Check bundled assets exist ───────────────────────────────────────────────
foreach ($asset in @("uspex.exe", "STMng-1.55.2-setup.exe")) {
  if (-not (Test-Path $asset)) {
    Write-Warning "$asset not found in project root — it will be missing from the installer."
  }
}

# ─── 3. Node / Tauri CLI ──────────────────────────────────────────────────────
if (-not $SkipNpmInstall) {
  Write-Host "[3/4] Installing Node dependencies..."
  npm install
} else {
  Write-Host "[3/4] Skipping npm install (SkipNpmInstall flag set)."
}

# ─── 4. Build Tauri NSIS installer ───────────────────────────────────────────
Write-Host "[4/4] Building Tauri Windows installer (NSIS)..."
# Use short target dir to avoid MAX_PATH issues on Windows
$env:CARGO_TARGET_DIR = "C:\ct"
npm run tauri:build

# ─── Done ─────────────────────────────────────────────────────────────────────
$bundle = "C:\ct\release\bundle\nsis"
if (Test-Path $bundle) {
  $installer = Get-ChildItem $bundle -Filter "*-setup.exe" | Select-Object -First 1
  if ($installer) {
    Write-Host ""
    Write-Host "SUCCESS! Installer: $($installer.FullName)"
    Write-Host "Size: $([math]::Round($installer.Length / 1MB, 1)) MB"
  }
} else {
  Write-Host "Build complete. Check C:\ct\release\bundle\ for output."
}

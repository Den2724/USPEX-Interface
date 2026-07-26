param(
  [string]$PythonExe = "python",
  [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

Write-Host "Building USPEX Runner executable..."

& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r requirements.txt
& $PythonExe -m pip install pyinstaller

if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist\USPEX_Runner") { Remove-Item "dist\USPEX_Runner" -Recurse -Force }

& $PythonExe -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --name USPEX_Runner `
  --noconsole `
  --collect-all flask `
  --collect-all jinja2 `
  --collect-all werkzeug `
  --collect-all click `
  --collect-all itsdangerous `
  --add-data "webapp;webapp" `
  --add-data "app;app" `
  launcher.py

Write-Host "Executable built at dist\USPEX_Runner\USPEX_Runner.exe"

if ($SkipInstaller) {
  Write-Host "SkipInstaller flag set. Done."
  exit 0
}

$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
  Write-Warning "Inno Setup not found. Install Inno Setup 6 and run packaging\installer.iss manually."
  exit 0
}

Write-Host "Building installer..."
& $iscc "packaging\installer.iss"
Write-Host "Installer is in dist_installer\"

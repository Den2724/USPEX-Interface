## Windows installer build

### Prerequisites
- Python 3.11+ in PATH
- Inno Setup 6 (optional, only if you want `.exe` installer)
- `STMng-1.55.2-setup.exe` in repository root (already used by installer script)

### Build executable + installer
```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1
```

### Build only executable
```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1 -SkipInstaller
```

### Output
- App folder: `dist\USPEX_Runner\`
- Installer: `dist_installer\USPEX_Runner_Setup.exe`

### Installer behavior
- Installs app to `Program Files\USPEX Runner`
- Creates Start Menu shortcut (and optional desktop shortcut)
- Optionally runs STMng installer if STMng is not installed

### Runtime config path
- Config is stored in `%APPDATA%\USPEX Runner\config.json`

#define MyAppName "USPEX Runner"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "USPEX"
#define MyAppExeName "USPEX_Runner.exe"

[Setup]
AppId={{7B8C6E1A-13C4-4E7D-99D1-4F0A0E65A2D2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\USPEX Runner
DefaultGroupName=USPEX Runner
DisableProgramGroupPage=yes
OutputDir=..\dist_installer
OutputBaseFilename=USPEX_Runner_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "installstmng"; Description: "Install STMng visualizer (recommended if not installed)"; GroupDescription: "Optional components:"; Flags: unchecked

[Files]
Source: "..\dist\USPEX_Runner\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "..\STMng-1.55.2-setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: not IsSTMngInstalled

[Icons]
Name: "{group}\USPEX Runner"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\USPEX Runner"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{tmp}\STMng-1.55.2-setup.exe"; Description: "Install STMng"; Flags: postinstall shellexec skipifsilent; Check: (not IsSTMngInstalled) and WizardIsTaskSelected('installstmng')
Filename: "{app}\{#MyAppExeName}"; Description: "Launch USPEX Runner"; Flags: nowait postinstall skipifsilent

[Code]
function IsSTMngInstalled(): Boolean;
begin
  Result := FileExists(ExpandConstant('{pf}\STMng\STMng.exe'));
end;

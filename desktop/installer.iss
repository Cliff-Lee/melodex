#define MyAppName "Melodex"
#define MyAppVersion "0.7.2"
#define MyAppPublisher "Melodex contributors"
#define MyAppExeName "Melodex.exe"

[Setup]
AppId={{9F4DD1D7-5318-4A74-91FB-3EE43A8D6407}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Melodex
DefaultGroupName=Melodex
OutputDir=dist
OutputBaseFilename=Melodex-Windows-x64-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "dist\Melodex\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Melodex"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Melodex"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Melodex"; Flags: nowait postinstall skipifsilent

#ifndef AppVersion
  #define AppVersion "1.3.0"
#endif
#ifndef NumericVersion
  #define NumericVersion "1.3.0.0"
#endif

[Setup]
AppId={{61D7D5A8-D455-4CDF-81DC-568616424406}
AppName=NetConfigLint
AppVersion={#AppVersion}
AppPublisher=NetConfigLint contributors
DefaultDirName={localappdata}\Programs\NetConfigLint
DefaultGroupName=NetConfigLint
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=NetConfigLint-{#AppVersion}-windows-x64-setup
SetupIconFile=..\netconfiglint\resources\icons\app.ico
UninstallDisplayIcon={app}\NetConfigLint.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
VersionInfoVersion={#NumericVersion}
VersionInfoDescription=NetConfigLint offline network configuration analyzer
#ifdef SignedBuild
SignTool=netconfiglint
SignedUninstaller=yes
#endif

[Files]
Source: "..\dist\NetConfigLint.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\NetConfigLint"; Filename: "{app}\NetConfigLint.exe"
Name: "{autodesktop}\NetConfigLint"; Filename: "{app}\NetConfigLint.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\NetConfigLint.exe"; Description: "Launch NetConfigLint"; Flags: nowait postinstall skipifsilent

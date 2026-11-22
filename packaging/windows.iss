#ifndef AppBuildDir
  #define AppBuildDir "..\dist\OriginExtract"
#endif
#ifndef SetupOutput
  #define SetupOutput "..\installers"
#endif

[Setup]
AppId={{BB3CE502-706C-4E94-9EE5-EAEBE861B2B5}
AppName=Origin Extract
AppVersion=2.1.0
AppVerName=Origin Extract 2.1.0
AppPublisher=Amir MEDDAS
AppCopyright=Copyright 2026 Amir MEDDAS
DefaultDirName={localappdata}\Programs\OriginExtract
DefaultGroupName=Origin Extract
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#SetupOutput}
OutputBaseFilename=OriginExtract-2.1.0-Windows-x64-Setup
SetupIconFile=..\assets\OriginExtract.ico
UninstallDisplayIcon={app}\OriginExtract.exe
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=100
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Creer un raccourci sur le bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Files]
Source: "{#AppBuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Origin Extract"; Filename: "{app}\OriginExtract.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Origin Extract"; Filename: "{app}\OriginExtract.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\OriginExtract.exe"; Description: "Lancer Origin Extract"; Flags: nowait postinstall skipifsilent

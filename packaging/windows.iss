#ifndef AppBuildDir
  #define AppBuildDir "..\dist\OriginExtract"
#endif
#ifndef SetupOutput
  #define SetupOutput "..\installers"
#endif

[Setup]
AppId={{BB3CE502-706C-4E94-9EE5-EAEBE861B2B5}
AppName=Origin Extract
AppVersion=2.1.2
AppVerName=Origin Extract 2.1.2
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
OutputBaseFilename=OriginExtract-2.1.2-Windows-x64-Setup
SetupIconFile=..\assets\OriginExtract.ico
UninstallDisplayIcon={app}\OriginExtract.exe
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=100
CloseApplications=yes
RestartApplications=no
ChangesAssociations=yes
#ifdef SignedRelease
SignTool=originextract
SignedUninstaller=yes
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#AppBuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Origin Extract"; Filename: "{app}\OriginExtract.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Origin Extract"; Filename: "{app}\OriginExtract.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\OriginExtract.exe"; Description: "Launch Origin Extract"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\Classes\.originpack"; ValueType: string; ValueName: ""; ValueData: "OriginExtract.Project"; Flags: createvalueifdoesntexist
Root: HKCU; Subkey: "Software\Classes\.originpack\OpenWithProgids"; ValueType: none; ValueName: "OriginExtract.Project"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\OriginExtract.Project"; ValueType: string; ValueName: ""; ValueData: "Origin Extract Project"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\OriginExtract.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\OriginExtract.exe,0"
Root: HKCU; Subkey: "Software\Classes\OriginExtract.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\OriginExtract.exe"" --open ""%1"""

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  CurrentHandler: String;
begin
  if CurUninstallStep = usPostUninstall then
    if RegQueryStringValue(HKCU, 'Software\Classes\.originpack', '', CurrentHandler) then
      if CurrentHandler = 'OriginExtract.Project' then
        RegDeleteValue(HKCU, 'Software\Classes\.originpack', '');
end;

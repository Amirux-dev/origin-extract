Origin Extract 2.1.2
Created by Amir MEDDAS

Compact desktop app for exporting Origin tables.
Black and purple interface, Fredoka and Nunito fonts, table and plot previews.

INSTALL
Windows: run OriginExtract-2.1.2-Windows-x64-Setup.exe.
Mac Apple Silicon: open the arm64 DMG, then drag Origin Extract to Applications.
Mac Intel: choose the x86_64 DMG.
Python and dependencies are bundled. Users do not need to install Python.
Requires Windows 10/11 x64 or macOS 12 and later.

USE
Open a project, select sheets, export. Column headers are included by default.
The ... menu opens portable sharing, the Mac/PC relay, the log and this guide.
The app, messages and Windows installer are in English. Scientific column
names and project contents keep their original language.

On Mac, .originpack files work offline. To convert a new .opju, connect to a
Windows PC with Origin Viewer using the optional relay.
Opening the relay address in a browser shows a welcome page. To connect the
Mac app, enter the PC address AND its connection key in Mac / PC > My Mac.

BUILD
GitHub > Actions > Installateurs > Run workflow builds and checks all 3 versions.
Installers are stored as workflow artifacts for 30 days.
This repository and the installers contain no local scientific projects.

Local Windows build:
python -m pip install -r requirements.txt pyinstaller==6.22.3
python packaging/build.py
On Mac, use requirements-macos.txt instead of requirements.txt.
Windows builds also require Inno Setup.

SIGNING
These builds have no Windows signing certificate or Apple Developer ID and
are not notarized. Operating systems may display a provenance warning or
block execution. Author metadata identifies Amir MEDDAS; it is not a verified
digital signature.

See GUIDE_WINDOWS_MAC.txt and CREDITS.txt.

LICENSE
Application code: MIT, Copyright (c) 2026 Amir MEDDAS. See LICENSE.
Third-party libraries and fonts retain their own licenses; see CREDITS.txt.
Scientific projects and measurement data are not part of this repository.

Code signing policy
See CODE_SIGNING_POLICY.txt. SignPath Foundation is a proposed provider;
no application has been submitted or accepted and no release has been signed.
Author, maintainer and proposed signing approver: Amir MEDDAS (@Amirux-dev).
The application transfers no information to other networked systems unless
specifically requested by the user or the person installing or operating it.
The optional user-started relay sends selected projects to the PC the user chose.
Signing scripts: packaging/SIGNING.txt. Signed builds require credentials and
fail rather than fall back to unsigned output. Current 2.1.2 downloads remain
unsigned development distributions. Signature trust is distinct from antivirus
approval and organization-specific application policies.

UNINSTALL
Windows: Installed apps > Origin Extract > Uninstall.
Mac: quit Origin Extract, then move it from Applications to the Trash.
Your exported tables and .originpack files are kept.

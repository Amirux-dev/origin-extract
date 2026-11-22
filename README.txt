Origin Extract 2.1
Auteur : Amir MEDDAS

Application compacte de conversion et d'export de tableaux Origin.
Interface noire/violette, polices Fredoka et Nunito, apercu des donnees et courbes.

INSTALLATION
Windows : lancer OriginExtract-2.1.0-Windows-x64-Setup.exe.
Mac Apple Silicon : ouvrir le DMG arm64, puis glisser l'application dans Applications.
Mac Intel : utiliser le DMG x86_64.
Les installateurs embarquent Python et les dependances : aucune installation
de Python n'est necessaire pour les utilisateurs.
Cibles : Windows 10/11 x64 ; macOS 12 ou plus recent, Apple Silicon ou Intel.

UTILISATION
Ouvrir un projet, cocher les feuilles, exporter. Les en-tetes sont inclus.
Le menu « ... » donne acces aux projets portables, au relais Mac/PC et au guide.

Sur Mac, les .originpack fonctionnent hors ligne. Pour convertir un nouveau
.opju, le relais utilise un PC Windows disposant d'Origin Viewer.

COMPILATION
Le workflow Installateurs fabrique et teste les trois versions.
GitHub > Actions > Installateurs > Run workflow.
Les fichiers sont disponibles dans les artefacts du workflow, pendant 30 jours.
Ce depot et les installateurs ne contiennent pas les donnees scientifiques locales.

Localement :
python -m pip install -r requirements.txt pyinstaller==6.22.3
python packaging/build.py
Sur Mac, utiliser requirements-macos.txt a la place de requirements.txt.
Sur Windows, le compilateur Inno Setup doit etre installe.

SIGNATURES
Ces builds ne disposent pas d'un certificat Windows ni d'un compte Apple
Developer configure pour la notarisation. Les systemes peuvent donc afficher
un avertissement de provenance. Les metadonnees affichent l'auteur Amir MEDDAS ;
cela ne remplace pas une signature numerique verifiee.

Voir GUIDE_WINDOWS_MAC.txt et CREDITS.txt.

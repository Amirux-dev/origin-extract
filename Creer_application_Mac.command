#!/bin/bash
set -e
app_dir="$(cd "$(dirname "$0")" && pwd)"
cd "$app_dir"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Installez Python 3.11 a 3.13 puis relancez ce fichier."
  read -r -p "Appuyez sur Entrée pour fermer. "
  exit 1
fi
if [ ! -x "$app_dir/.venv-mac/bin/python" ]; then
  python3 -m venv "$app_dir/.venv-mac"
fi
"$app_dir/.venv-mac/bin/python" -m pip install -r requirements.txt 'pyinstaller==6.22.3'
"$app_dir/.venv-mac/bin/python" -m PyInstaller --noconfirm --windowed --name 'Origin Extract' \
  --distpath "$app_dir/Application_Mac" --workpath "$app_dir/.construction-mac" \
  --specpath "$app_dir/.construction-mac" \
  --add-data "$app_dir/Exemples:Exemples" \
  --add-data "$app_dir/noms_colonnes.json:." \
  "$app_dir/lancer_origin_extract.py"
echo "Application creee dans Application_Mac/Origin Extract.app"
open "$app_dir/Application_Mac"

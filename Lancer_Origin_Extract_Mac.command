#!/bin/bash
set -e
app_dir="$(cd "$(dirname "$0")" && pwd)"
cd "$app_dir"
echo "Origin Extract · préparation du lancement"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Installez Python 3.10 ou plus récent depuis https://www.python.org/downloads/macos/ puis relancez ce fichier."
  read -r -p "Appuyez sur Entrée pour fermer. "
  exit 1
fi
if ! python3 -c 'import sys; assert sys.version_info >= (3,10)' >/dev/null 2>&1; then
  echo "Python 3.10 ou plus récent est nécessaire."
  read -r -p "Appuyez sur Entrée pour fermer. "
  exit 1
fi
if [ ! -x "$app_dir/.venv-mac/bin/python" ]; then
  python3 -m venv "$app_dir/.venv-mac"
fi
if ! "$app_dir/.venv-mac/bin/python" -c 'import PySide6.QtWidgets' >/dev/null 2>&1; then
  echo "Installation de l’interface (une seule fois, connexion Internet requise)…"
  "$app_dir/.venv-mac/bin/python" -m pip install -r "$app_dir/requirements.txt"
fi
exec "$app_dir/.venv-mac/bin/python" "$app_dir/lancer_origin_extract.py"

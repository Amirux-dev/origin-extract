"""Journaux locaux : les projets et les tableaux ne sont jamais copiés ici."""
from datetime import datetime
import os
from pathlib import Path
import sys
import uuid


def save_conversion_log(data):
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'OriginExtract/Logs'
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Logs/OriginExtract'
    else:
        base = Path.home() / '.local/state/OriginExtract'
    base.mkdir(parents=True, exist_ok=True)
    path = base / f'conversion-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.log'
    path.write_bytes(data)
    return path

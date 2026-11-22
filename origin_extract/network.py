"""Diagnostic Windows en lecture seule et accès aux réglages natifs."""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys


def program_paths():
    paths = {str(Path(sys.executable).resolve())}
    if sys.platform == 'win32':
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.kernel32.GetModuleFileNameW(None, buffer, len(buffer)):
            paths.add(buffer.value)
    return sorted(paths)


def firewall_status():
    if sys.platform != 'win32':
        return {}
    quoted = ','.join("'" + path.replace("'", "''") + "'" for path in program_paths())
    script = """$ErrorActionPreference='Stop'
$programs=@(PROGRAMS)
$rules=@(Get-NetFirewallApplicationFilter | Where-Object { $programs -contains $_.Program } |
    Get-NetFirewallRule | Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Block' } |
    Select-Object DisplayName,@{Name='Profile';Expression={[int]$_.Profile}})
$profiles=@(Get-NetConnectionProfile | Select-Object Name,@{Name='Category';Expression={[int]$_.NetworkCategory}})
@{rules=$rules;profiles=$profiles} | ConvertTo-Json -Depth 4 -Compress
""".replace('PROGRAMS', quoted)
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                            '[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;' + script],
                            capture_output=True, timeout=15,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        return {'unavailable': True}
    return json.loads(result.stdout.decode('utf-8-sig', errors='replace'))


def firewall_message(status):
    if status.get('unavailable'):
        return 'Diagnostic indisponible. Ouvrez le pare-feu pour vérifier les autorisations.'
    if status.get('rules'):
        return 'Windows bloque ce programme. Ouvrez le pare-feu pour le réautoriser.'
    profiles = status.get('profiles', [])
    if profiles and all(item.get('Category') == 0 for item in profiles):
        return 'Réseau public : utilisez un réseau privé de confiance ou Tailscale.'
    return 'Le Mac doit joindre cette adresse. Un test local ne vérifie pas le pare-feu.'


def open_firewall_settings():
    subprocess.Popen([str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/control.exe'),
                      '/name', 'Microsoft.WindowsFirewall', '/page', 'pageConfigureApps'])

"""Import an existing Developer ID into an ephemeral macOS CI keychain."""
import base64
import json
import os
from pathlib import Path
import secrets
import shlex
import sys
from signing import private_run

REQUIRED = ('APPLE_CERTIFICATE_P12_BASE64', 'APPLE_CERTIFICATE_PASSWORD',
            'APPLE_NOTARY_API_KEY_BASE64', 'APPLE_NOTARY_KEY_ID', 'APPLE_NOTARY_ISSUER_ID')


def locations():
    root = Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    directory = root / 'OriginExtract-signing'
    if directory.exists() and not directory.resolve().is_relative_to(root):
        raise RuntimeError('Unexpected signing directory.')
    return directory, directory / 'release.keychain-db'


def cleanup():
    directory, keychain = locations()
    if not directory.exists():
        return
    previous = directory / 'previous-keychains.json'
    if previous.exists():
        private_run(['security', 'list-keychains', '-d', 'user', '-s', *json.loads(previous.read_text())])
    if keychain.exists():
        private_run(['security', 'delete-keychain', str(keychain)])
    # Only our generated secrets, never arbitrary paths or user keychains.
    for name in ('certificate.p12', 'notary.p8', 'previous-keychains.json'):
        path = directory / name
        if path.exists():
            path.unlink()
    if not any(directory.iterdir()):
        directory.rmdir()


def setup():
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        raise RuntimeError('Missing GitHub signing secrets: ' + ', '.join(missing))
    directory, keychain = locations()
    directory.mkdir(mode=0o700, exist_ok=False)
    password = secrets.token_urlsafe(32)
    certificate = directory / 'certificate.p12'
    api_key = directory / 'notary.p8'
    try:
        for path, name in ((certificate, 'APPLE_CERTIFICATE_P12_BASE64'), (api_key, 'APPLE_NOTARY_API_KEY_BASE64')):
            with path.open('xb') as stream:
                path.chmod(0o600)
                stream.write(base64.b64decode(os.environ[name], validate=True))
        previous = shlex.split(private_run(['security', 'list-keychains', '-d', 'user']).stdout.decode('utf-8'))
        (directory / 'previous-keychains.json').write_text(json.dumps(previous), encoding='utf-8')
        private_run(['security', 'create-keychain', '-p', password, str(keychain)])
        private_run(['security', 'set-keychain-settings', '-lut', '21600', str(keychain)])
        private_run(['security', 'unlock-keychain', '-p', password, str(keychain)])
        private_run(['security', 'import', str(certificate), '-P', os.environ['APPLE_CERTIFICATE_PASSWORD'],
                     '-k', str(keychain), '-T', '/usr/bin/codesign', '-T', '/usr/bin/security'])
        private_run(['security', 'set-key-partition-list', '-S', 'apple-tool:,apple:', '-s', '-k', password, str(keychain)])
        private_run(['security', 'list-keychains', '-d', 'user', '-s', str(keychain), *previous])
        private_run(['xcrun', 'notarytool', 'store-credentials', 'OriginExtract-release',
                     '--key', str(api_key), '--key-id', os.environ['APPLE_NOTARY_KEY_ID'],
                     '--issuer', os.environ['APPLE_NOTARY_ISSUER_ID'], '--keychain', str(keychain)])
        with Path(os.environ['GITHUB_ENV']).open('a', encoding='utf-8') as output:
            output.write(f'MACOS_SIGNING_KEYCHAIN={keychain}\nMACOS_NOTARY_PROFILE=OriginExtract-release\n')
    except Exception:
        cleanup()
        raise
    finally:
        for path in (certificate, api_key):
            if path.exists():
                path.unlink()


if __name__ == '__main__':
    if sys.platform != 'darwin':
        raise SystemExit('Apple keychain setup must run on macOS.')
    if sys.argv[1:] == ['setup']:
        setup()
    elif sys.argv[1:] == ['cleanup']:
        cleanup()
    else:
        raise SystemExit('Usage: apple_ci.py setup|cleanup')

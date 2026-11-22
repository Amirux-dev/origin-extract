"""Release signing. Missing credentials never fall back to an unsigned release."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


@dataclass(frozen=True)
class Signing:
    platform: str
    identity: str = ''
    keychain: str = ''
    notary_profile: str = ''
    windows_thumbprint: str = ''
    windows_command: tuple[str, ...] = ()
    timestamp_url: str = 'http://timestamp.digicert.com'


def configuration(platform, env=None):
    env = os.environ if env is None else env
    if platform == 'darwin':
        identity = env.get('MACOS_SIGNING_IDENTITY', '').strip()
        profile = env.get('MACOS_NOTARY_PROFILE', '').strip()
        if not identity.startswith('Developer ID Application: ') or not profile:
            raise ValueError('Signed Mac release needs a Developer ID Application identity and MACOS_NOTARY_PROFILE. See packaging/SIGNING.txt.')
        return Signing(platform, identity=identity, keychain=env.get('MACOS_SIGNING_KEYCHAIN', ''), notary_profile=profile)
    if platform == 'win32':
        thumbprint = env.get('WINDOWS_CERT_SHA1', '').replace(' ', '').upper()
        command = env.get('WINDOWS_SIGN_COMMAND_JSON', '')
        if command and thumbprint:
            raise ValueError('Choose either WINDOWS_CERT_SHA1 or WINDOWS_SIGN_COMMAND_JSON.')
        if command:
            try:
                command = json.loads(command)
            except json.JSONDecodeError:
                raise ValueError('WINDOWS_SIGN_COMMAND_JSON must be a JSON argument array.') from None
            if (not isinstance(command, list) or not command or
                    not all(isinstance(arg, str) and arg for arg in command) or
                    command.count('{file}') != 1):
                raise ValueError('Windows signing command needs exactly one standalone {file} argument.')
            return Signing(platform, windows_command=tuple(command))
        if not re.fullmatch('[0-9A-F]{40}', thumbprint):
            raise ValueError('Signed Windows release needs a trusted signing provider or certificate. See packaging/SIGNING.txt.')
        return Signing(platform, windows_thumbprint=thumbprint,
                       timestamp_url=env.get('WINDOWS_TIMESTAMP_URL', 'http://timestamp.digicert.com'))
    raise ValueError('Release signing is supported on Windows and macOS only.')


def private_run(arguments):
    """Do not expose signing-provider credentials through logs or exceptions."""
    result = subprocess.run([str(arg) for arg in arguments], capture_output=True)
    if result.returncode:
        raise RuntimeError(f'Signing command failed ({Path(arguments[0]).name}, exit {result.returncode}).')
    return result


def find_signtool():
    configured = os.environ.get('SIGNTOOL') or shutil.which('signtool.exe')
    if configured:
        return str(configured)
    sdk = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Windows Kits/10/bin'
    candidates = sorted(sdk.glob('*/x64/signtool.exe'), reverse=True)
    if not candidates:
        raise RuntimeError('Install the Windows SDK signing tools or set SIGNTOOL.')
    return str(candidates[0])


def verify_windows(path, timestamp=False):
    command = [find_signtool(), 'verify', '/pa', '/all']
    if timestamp:
        command.append('/tw')
    private_run(command + [str(path)])


def sign_windows(path, config):
    path = Path(path).resolve(strict=True)
    if config.windows_command:
        command = [str(path) if arg == '{file}' else arg for arg in config.windows_command]
    else:
        command = [find_signtool(), 'sign', '/sha1', config.windows_thumbprint, '/s', 'My',
                   '/fd', 'SHA256', '/tr', config.timestamp_url, '/td', 'SHA256', '/d', 'Origin Extract', str(path)]
    private_run(command)
    verify_windows(path, timestamp=True)


def sign_windows_tree(folder, config):
    # Sign only this project's executable. In particular, SignPath Foundation
    # forbids signing upstream libraries with the project's certificate.
    sign_windows(Path(folder) / 'OriginExtract.exe', config)


def mac_sign_arguments(config):
    command = ['codesign', '--force', '--timestamp', '--options', 'runtime', '--sign', config.identity]
    if config.keychain:
        command += ['--keychain', config.keychain]
    return command


def notarize(path, config, report, staple_target=None):
    command = ['xcrun', 'notarytool', 'submit', str(path), '--keychain-profile', config.notary_profile,
               '--wait', '--timeout', '20m', '--output-format', 'json']
    if config.keychain:
        command += ['--keychain', config.keychain]
    result = private_run(command)
    try:
        status = json.loads(result.stdout)
    except (ValueError, UnicodeDecodeError):
        raise RuntimeError('Apple returned an unreadable notarization response.') from None
    Path(report).write_text(json.dumps(status, indent=2), encoding='utf-8')
    if status.get('status') != 'Accepted':
        raise RuntimeError(f"Apple did not accept notarization (submission {status.get('id', 'unknown')}).")
    target = path if staple_target is None else staple_target
    private_run(['xcrun', 'stapler', 'staple', str(target)])
    private_run(['xcrun', 'stapler', 'validate', str(target)])


def notarize_app(bundle, config, work, output):
    # Root signature is renewed after Info.plist changes; PyInstaller has already
    # signed nested code with this same identity and hardened runtime enabled.
    private_run(mac_sign_arguments(config) + [str(bundle)])
    private_run(['codesign', '--verify', '--deep', '--strict', str(bundle)])
    archive = Path(work) / 'notarization-app.zip'
    private_run(['ditto', '-c', '-k', '--keepParent', str(bundle), str(archive)])
    # Staple the app, not its ZIP container, after Apple's acceptance.
    notarize(archive, config, Path(output) / 'notarization-app.json', staple_target=bundle)
    private_run(['spctl', '--assess', '--type', 'execute', '--verbose', str(bundle)])


if __name__ == '__main__':
    if sys.argv[1:] == ['--check']:
        configuration(sys.platform)
        print('Signing configuration is present. Certificate availability and trust are verified during signing.')
    elif len(sys.argv) == 3 and sys.argv[1] == '--windows-file':
        if sys.platform != 'win32':
            raise SystemExit('Windows signing must run on Windows.')
        sign_windows(sys.argv[2], configuration('win32'))
    else:
        raise SystemExit('Usage: signing.py --check | --windows-file FILE')

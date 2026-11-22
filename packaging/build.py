"""Compilation native : Windows -> .exe d'installation ; macOS -> .app et .dmg."""
from pathlib import Path
import os
import platform
import plistlib
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION = '2.1.0'


def run(*arguments, **kwargs):
    print('>', ' '.join(map(str, arguments)), flush=True)
    subprocess.run(list(map(str, arguments)), check=True, **kwargs)


def icons():
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    sys.path.insert(0, str(ROOT))
    from PySide6.QtWidgets import QApplication
    from origin_extract.ui import app_icon
    app = QApplication.instance() or QApplication([])
    icon = app_icon(1024)
    assert icon.pixmap(256).save(str(ROOT / 'assets/OriginExtract.ico'))
    if sys.platform == 'darwin':
        directory = ROOT / '.build/OriginExtract.iconset'
        directory.mkdir(parents=True, exist_ok=True)
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                suffix = '@2x' if scale == 2 else ''
                path = directory / f'icon_{size}x{size}{suffix}.png'
                assert icon.pixmap(size * scale).save(str(path))
        run('iconutil', '-c', 'icns', directory, '-o', ROOT / 'assets/OriginExtract.icns')
    return app


def find_iscc():
    candidates = [os.environ.get('ISCC'), shutil.which('ISCC'),
                  str(ROOT / 'Developpement/outils/InnoSetup/ISCC.exe')]
    for folder in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles')):
        if folder:
            candidates.extend(str(Path(folder) / f'Inno Setup {version}/ISCC.exe') for version in (7, 6))
    return next((p for p in candidates if p and Path(p).is_file()), None)


def main():
    os.chdir(ROOT)
    assert (ROOT / 'dist').resolve().is_relative_to(ROOT)
    assert (ROOT / '.build').resolve().is_relative_to(ROOT)
    app = icons()
    output = ROOT / 'installers'
    output.mkdir(exist_ok=True)
    commands = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
                '--name', 'OriginExtract', '--distpath', str(ROOT / 'dist'),
                '--exclude-module', 'tkinter', '--exclude-module', '_tkinter',
                '--workpath', str(ROOT / '.build/work'), '--specpath', str(ROOT / '.build'),
                '--add-data', f'{ROOT / "assets"}{os.pathsep}assets',
                '--add-data', f'{ROOT / "noms_colonnes.json"}{os.pathsep}.',
                '--add-data', f'{ROOT / "GUIDE_WINDOWS_MAC.txt"}{os.pathsep}.',
                '--add-data', f'{ROOT / "CREDITS.txt"}{os.pathsep}.',
                '--add-data', f'{ROOT / "README.txt"}{os.pathsep}.',
                '--copy-metadata', 'PySide6-Essentials', '--copy-metadata', 'shiboken6']
    if sys.platform == 'win32':
        commands += ['--icon', str(ROOT / 'assets/OriginExtract.ico'),
                     '--version-file', str(ROOT / 'packaging/windows-version.txt')]
    elif sys.platform == 'darwin':
        commands += ['--icon', str(ROOT / 'assets/OriginExtract.icns'),
                     '--osx-bundle-identifier', 'fr.amirmeddas.originextract']
    else:
        raise SystemExit('Compilez les installateurs Windows sur Windows et les DMG sur macOS.')
    commands += [str(ROOT / 'lancer_origin_extract.py')]
    run(*commands)
    if sys.platform == 'win32':
        compiler = find_iscc()
        if not compiler:
            raise SystemExit('Inno Setup est necessaire : https://jrsoftware.org/isdl.php')
        run(compiler, f'/DAppBuildDir={ROOT / "dist/OriginExtract"}',
            f'/DSetupOutput={output}', ROOT / 'packaging/windows.iss')
    else:
        bundle = ROOT / 'dist/OriginExtract.app'
        info = bundle / 'Contents/Info.plist'
        content = plistlib.loads(info.read_bytes())
        content.update(CFBundleDisplayName='Origin Extract', CFBundleName='Origin Extract',
                       CFBundleShortVersionString=VERSION, CFBundleVersion=VERSION,
                       NSHumanReadableCopyright='Copyright 2026 Amir MEDDAS',
                       LSMinimumSystemVersion='12.0')
        content['CFBundleDocumentTypes'] = [dict(CFBundleTypeName='Origin Extract Project',
                                                CFBundleTypeRole='Viewer', LSHandlerRank='Owner',
                                                LSItemContentTypes=['fr.amirmeddas.originpack'])]
        content['UTExportedTypeDeclarations'] = [dict(UTTypeIdentifier='fr.amirmeddas.originpack',
                                                      UTTypeDescription='Origin Extract Project',
                                                      UTTypeConformsTo=['public.data', 'public.archive'],
                                                      UTTypeTagSpecification={'public.filename-extension': ['originpack'],
                                                                              'public.mime-type': 'application/x-origin-extract'})]
        info.write_bytes(plistlib.dumps(content))
        # Signature ad hoc requise pour le fonctionnement Apple Silicon.
        # Une signature Developer ID et la notarisation restent distinctes.
        run('codesign', '--force', '--deep', '--sign', '-', bundle)
        run('codesign', '--verify', '--deep', '--strict', bundle)
        executable = bundle / 'Contents/MacOS/OriginExtract'
        run(executable, '--smoke-test', '--diagnostic-file', output / 'smoke-macos.json',
            env=dict(os.environ, QT_QPA_PLATFORM='offscreen'))
        stage = ROOT / '.build/dmg'
        stage.mkdir(parents=True, exist_ok=True)
        target = stage / 'Origin Extract.app'
        if target.exists():
            raise SystemExit('Un precedent dossier de fabrication DMG existe. Utilisez un dossier de compilation neuf.')
        run('ditto', bundle, target)
        (stage / 'Applications').symlink_to('/Applications')
        name = output / f'OriginExtract-{VERSION}-Mac-{platform.machine()}.dmg'
        run('hdiutil', 'create', '-volname', 'Origin Extract', '-srcfolder', stage,
            '-ov', '-format', 'UDZO', name)
    print('Installateurs :', output, flush=True)


if __name__ == '__main__':
    main()

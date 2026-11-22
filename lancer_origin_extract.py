"""Lanceur commun Windows/macOS, sans dépendance à Origin Viewer sur Mac."""
import argparse
import contextlib
import json
from pathlib import Path
import sys
import traceback


def conversion_worker(arguments):
    log_path = None
    if '--worker-log' in arguments:
        at = arguments.index('--worker-log')
        log_path = Path(arguments[at + 1])
        del arguments[at:at + 2]
    sys.argv = ['export_origin.py'] + arguments
    def execute():
        from export_origin import main as convert
        try:
            return convert() or 0
        except Exception:
            traceback.print_exc()
            return 1
    if log_path:
        with log_path.open('w', encoding='utf-8', buffering=1) as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                return execute()
    return execute()


def smoke_test(destination=None):
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase
    from origin_extract import __version__, __author__
    from origin_extract.ui import Window
    app = QApplication(sys.argv[:1])
    window = Window()
    families = QFontDatabase.families()
    assert 'Fredoka' in families and 'Nunito' in families
    assert window.width() <= 940 and window.height() <= 640
    assert __author__ == 'Amir MEDDAS'
    result = dict(status='ok', version=__version__, author=__author__,
                  width=window.width(), height=window.height(), fonts=['Fredoka', 'Nunito'])
    if destination:
        Path(destination).write_text(json.dumps(result, indent=2), encoding='utf-8')
    window.close()
    return 0

def main():
    if '--convert-worker' in sys.argv:
        arguments = sys.argv[1:]
        arguments.remove('--convert-worker')
        return conversion_worker(arguments)
    parser = argparse.ArgumentParser(description='Origin Extract · Windows et Mac')
    parser.add_argument('--open', dest='project')
    parser.add_argument('--welcome', action='store_true')
    parser.add_argument('--smoke-test', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--diagnostic-file', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.smoke_test:
        return smoke_test(args.diagnostic_file)
    project = args.project
    example = Path(__file__).resolve().parent / 'Exemples/from6jun2026_AGH.originpack'
    if not project and not args.welcome and example.exists():
        project = str(example)
    from origin_extract.ui import run
    return run(project)

if __name__ == '__main__':
    sys.exit(main())

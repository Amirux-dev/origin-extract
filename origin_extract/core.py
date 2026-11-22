"""Lecture, vérification et export portables. Aucun import spécifique à Windows."""
from __future__ import annotations

import copy
import csv
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import threading
import uuid
import zipfile
from .number_text import decimal_text

PACK_FORMAT = 'origin-extract/1'
MAX_PACK_BYTES = 1024 * 1024 * 1024
MAX_SHEET_BYTES = 256 * 1024 * 1024


class Cancelled(Exception):
    pass


def check_cancel(stop):
    if stop is not None and stop.is_set():
        raise Cancelled("Operation stopped. Existing files have been kept.")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(value, limit=110):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(value)).strip(' .') or 'Sans_nom'
    if re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?', name):
        name = '_' + name
    return name[:limit].rstrip(' .')


def column_letter(index):
    result = ''
    while index:
        index, rest = divmod(index - 1, 26)
        result = chr(65 + rest) + result
    return result


def relative_path(value):
    # Les packs utilisent exclusivement des chemins relatifs POSIX.
    if '\\' in value or ':' in value:
        raise ValueError('Invalid table path in the portable project.')
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(p in ('..', '.') for p in path.parts):
        raise ValueError('Invalid table path in the portable project.')
    return path


@dataclass
class Sheet:
    record: dict
    content: bytes
    headers: list[str]
    rows: list[list[str]]

    @property
    def name(self):
        return self.record.get('sheet') or self.record.get('title') or self.record.get('book', 'Feuille')

    @property
    def reconstructed(self):
        return any(c.get('reconstructed_name') for c in self.record.get('column_metadata', []) or [])


@dataclass
class Project:
    name: str
    source_hash: str
    sheets: list[Sheet]
    skipped: list[dict] = field(default_factory=list)
    source: str = ''
    warnings: list[dict] = field(default_factory=list)

    @property
    def row_count(self):
        return sum(len(sheet.rows) for sheet in self.sheets)


def decode_sheet(record, raw, header_lines=1, separator='\t', decimal_comma=False):
    if len(raw) > MAX_SHEET_BYTES:
        raise ValueError('This table exceeds the 256 MB limit.')
    if record.get('sha256') and digest(raw) != record['sha256']:
        raise ValueError(f"The file {record.get('sheet', '')} has changed or is incomplete (SHA256).")
    if separator not in ('\t', ';', ','):
        raise ValueError('Unsupported table separator.')
    parsed = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), delimiter=separator))
    count = record.get('columns')
    if not isinstance(count, int) or not 1 <= count <= 100000:
        raise ValueError('Invalid column count.')
    if header_lines not in (0, 1):
        raise ValueError("Unsupported header row count.")
    if header_lines:
        if not parsed:
            raise ValueError('The table is empty.')
        headers, rows = parsed[0], parsed[1:]
    else:
        metadata = record.get('column_metadata') or []
        headers = [metadata[i].get('exported_header') if i < len(metadata) else column_letter(i + 1)
                   for i in range(count)]
        rows = parsed
    if len(headers) != count or any(len(row) != count for row in rows):
        raise ValueError(f"Inconsistent columns in {record.get('sheet', 'the table')}.")
    if len(rows) != record.get('rows'):
        raise ValueError(f"Inconsistent row count in {record.get('sheet', 'the table')}.")
    if decimal_comma:
        rows = [[decimal_text(v, True) for v in row] for row in rows]
    if not header_lines or separator != '\t' or decimal_comma:
        output = io.StringIO(newline='')
        csv.writer(output, delimiter='\t', lineterminator='\n').writerows([headers] + rows)
        raw = output.getvalue().encode('utf-8')
    result = copy.deepcopy(record)
    result['sha256'] = digest(raw)
    return Sheet(result, raw, headers, rows)


def load_export(folder, stop=None, log=lambda message: None):
    folder = Path(folder).resolve()
    if not (folder / '_rapport.json').exists() and (folder.parent / '_rapport.json').exists():
        folder = folder.parent
    report = json.loads((folder / '_rapport.json').read_text(encoding='utf-8'))
    records = report.get('sheets', [])
    if not records:
        raise ValueError('This folder contains no exported tables.')
    sheets = []
    for item in records:
        check_cancel(stop)
        file = str(item['file']).replace('\\', '/')
        rel = relative_path(file)
        path = folder.joinpath(*rel.parts)
        if not path.exists():
            # Prendre en compte un dossier renommé, sans jamais suivre un chemin hors du projet.
            candidates = list(folder.rglob(rel.name))
            if len(candidates) != 1:
                raise ValueError(f'Missing or ambiguous table: {rel.name}')
            path = candidates[0]
        if not path.resolve().is_relative_to(folder):
            raise ValueError('A table is outside the project folder.')
        sheets.append(decode_sheet(item, path.read_bytes(), report.get('header_lines', 0),
                                   report.get('separator', '\t'), report.get('decimals') == 'virgule'))
        log(f"Checked: {item.get('sheet', rel.name)}")
    source = Path(report.get('project') or folder.name)
    source_hash = digest(source.read_bytes()) if source.is_file() else report.get('source_sha256', '')
    name = Path(re.split(r'[/\\]', str(source))[-1]).stem
    return Project(name, source_hash, sheets, report.get('skipped', []), str(folder), report.get('warnings', []))


def pack_bytes(project, stop=None):
    stream = io.BytesIO()
    records = []
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for index, sheet in enumerate(project.sheets):
            check_cancel(stop)
            record = copy.deepcopy(sheet.record)
            record['file'] = f'tables/{index:04d}.tsv'
            record['sha256'] = digest(sheet.content)
            records.append(record)
            archive.writestr(record['file'], sheet.content)
        manifest = dict(format=PACK_FORMAT, name=project.name, source_sha256=project.source_hash,
                        header_lines=1, sheets=records, skipped=project.skipped, warnings=project.warnings)
        archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    return stream.getvalue()


def write_pack(project, destination, stop=None):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError('This portable project already exists. Choose another name.')
    data = pack_bytes(project, stop)
    check_cancel(stop)
    with destination.open('xb') as stream:
        stream.write(data)
    return destination


def load_pack(source, stop=None):
    stream = io.BytesIO(source) if isinstance(source, bytes) else Path(source)
    with zipfile.ZipFile(stream) as archive:
        entries = archive.infolist()
        if len(entries) > 50000 or sum(i.file_size for i in entries) > MAX_PACK_BYTES:
            raise ValueError('The portable project exceeds the size limit.')
        if len({i.filename for i in entries}) != len(entries):
            raise ValueError('The portable project contains duplicate filenames.')
        if 'manifest.json' not in archive.namelist() or archive.getinfo('manifest.json').file_size > 5 * 1024 * 1024:
            raise ValueError('The file does not contain a valid Origin Extract manifest.')
        manifest = json.loads(archive.read('manifest.json').decode('utf-8'))
        if manifest.get('format') != PACK_FORMAT or manifest.get('header_lines') != 1:
            raise ValueError('Unsupported portable project version.')
        records = manifest.get('sheets')
        if not isinstance(records, list) or not records:
            raise ValueError('The project contains no tables.')
        sheets = []
        for record in records:
            check_cancel(stop)
            name = str(relative_path(record['file']))
            if archive.getinfo(name).file_size > MAX_SHEET_BYTES:
                raise ValueError('A table exceeds the size limit.')
            sheets.append(decode_sheet(record, archive.read(name), 1))
    return Project(str(manifest.get('name') or 'Projet'), str(manifest.get('source_sha256') or ''),
                   sheets, manifest.get('skipped', []), '' if isinstance(source, bytes) else str(source),
                   manifest.get('warnings', []))


@dataclass
class ExportOptions:
    extension: str = 'txt'
    separator: str = '\t'
    include_headers: bool = True
    decimal_point: bool = True


NUMERIC_DOT = re.compile(r'^[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?$')
NUMERIC_COMMA = re.compile(r'^[+-]?(?:\d+,\d*|,\d+)(?:[eE][+-]?\d+)?$')


def render_sheet(sheet, options):
    if options.include_headers and options.separator == '\t' and options.decimal_point:
        return sheet.content
    output = io.StringIO(newline='')
    writer = csv.writer(output, delimiter=options.separator, lineterminator='\n')
    if options.include_headers:
        writer.writerow(sheet.headers)
    for row in sheet.rows:
        if options.decimal_point:
            row = [decimal_text(v, True) for v in row]
        else:
            row = [decimal_text(v, False) for v in row]
        writer.writerow(row)
    return output.getvalue().encode('utf-8')


def export_project(project, destination, selected=None, options=None, stop=None,
                   progress=lambda current, total, message: None):
    options = options or ExportOptions()
    if options.extension not in ('txt', 'csv') or options.separator not in ('\t', ';', ','):
        raise ValueError("Invalid export format.")
    indices = list(range(len(project.sheets))) if selected is None else sorted(set(selected))
    if not indices or any(i < 0 or i >= len(project.sheets) for i in indices):
        raise ValueError('Select at least one table.')
    base = Path(destination).resolve()
    base.mkdir(parents=True, exist_ok=True)
    check_cancel(stop)
    name = f'{safe_name(project.name, 60)}_{datetime.now():%Y%m%d_%H%M%S}'
    folder = base / name
    suffix = 2
    while folder.exists():
        folder = base / f'{name}_{suffix}'
        suffix += 1
    staging = base / f'.origin_extract_{uuid.uuid4().hex}.partiel'
    staging.mkdir()
    records = []
    try:
        for count, index in enumerate(indices, 1):
            check_cancel(stop)
            sheet = project.sheets[index]
            folders = [safe_name(p, 45) for p in re.split(r'[/\\]', sheet.record.get('folder', '')) if p]
            parent = staging.joinpath(*folders)
            parent.mkdir(parents=True, exist_ok=True)
            stem = safe_name(sheet.name)
            path = parent / f'{stem}.{options.extension}'
            counter = 2
            while path.exists():
                path = parent / f'{stem}__{counter}.{options.extension}'
                counter += 1
            data = render_sheet(sheet, options)
            with path.open('xb') as stream:
                stream.write(data)
            record = copy.deepcopy(sheet.record)
            record.update(file=path.relative_to(staging).as_posix(), sha256=digest(data))
            records.append(record)
            progress(count, len(indices), sheet.name)
        check_cancel(stop)
        report = dict(project=project.name, source_sha256=project.source_hash, status='terminé',
                      format=f'UTF-8, {options.extension.upper()}',
                      separator=options.separator, header_lines=int(options.include_headers),
                      decimals='point' if options.decimal_point else 'virgule', sheets=records,
                      skipped=project.skipped, warnings=project.warnings)
        (staging / '_rapport.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        with (staging / '_index.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            fields = ['book', 'sheet', 'rows', 'columns', 'file', 'sha256']
            writer = csv.DictWriter(stream, fieldnames=fields, delimiter=';')
            writer.writeheader()
            writer.writerows({key: r.get(key, '') for key in fields} for r in records)
        staging.rename(folder)
        return folder
    except Exception:
        # Le dossier n'est jamais présenté comme un export terminé ; on conserve
        # le partiel pour inspection au lieu de supprimer des fichiers.
        (staging / '_interrompu.txt').write_text('Export interrupted or incomplete.', encoding='utf-8')
        raise


def convert_windows(project, viewer, destination, stop=None, log=lambda message: None):
    """Isoler l'automatisation Windows du fil Qt et du relais HTTP."""
    import sys
    if sys.platform != 'win32':
        raise RuntimeError('OPJU conversion requires the Windows relay. Open an .originpack to work offline.')
    import os
    import subprocess
    root = Path(__file__).resolve().parents[1]
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    cancel_path = destination / ('_cancel_' + uuid.uuid4().hex)
    log_path = destination / ('_conversion_' + uuid.uuid4().hex + '.log')
    entry = [sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, '-u', str(root / 'lancer_origin_extract.py')]
    command = entry + ['--convert-worker', '--worker-log', str(log_path), '--no-gui',
               '--project', str(Path(project).resolve()), '--viewer', str(Path(viewer).resolve()),
               '--output', str(destination), '--cancel-file', str(cancel_path)]
    environment = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1', PYTHONUTF8='1')
    check_cancel(stop)
    process = subprocess.Popen(command, cwd=root, env=environment, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    offset, pending = 0, b''
    failure = ''
    def read_log(final=False):
        nonlocal offset, pending, failure
        if log_path.exists():
            with log_path.open('rb') as stream:
                stream.seek(offset)
                chunk = stream.read()
                offset += len(chunk)
                pending += chunk
        while b'\n' in pending or (final and pending):
            line, sep, rest = pending.partition(b'\n')
            pending = rest if sep else b''
            message = line.decode('utf-8', errors='replace').rstrip()
            if message:
                log(message)
                if 'Error:' in message or 'Exception:' in message:
                    failure = message
    while process.poll() is None:
        if stop is not None and stop.is_set() and not cancel_path.exists():
            cancel_path.write_text('stop', encoding='ascii')
        read_log()
        import time
        time.sleep(.1)
    read_log(final=True)
    check_cancel(stop)
    if process.returncode:
        message = failure or 'Windows conversion failed.'
        try:
            from .diagnostics import save_conversion_log
            diagnostic = save_conversion_log(log_path.read_bytes() if log_path.exists() else message.encode('utf-8'))
            message += f'\nLog: {diagnostic}'
        except OSError:
            pass
        raise RuntimeError(message)
    reports = list(destination.glob('*/_rapport.json'))
    complete = [r for r in reports if json.loads(r.read_text(encoding='utf-8')).get('status') == 'terminé']
    if len(complete) != 1:
        raise RuntimeError('The Windows converter did not produce a single complete export.')
    return load_export(complete[0].parent, stop, log)

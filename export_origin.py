"""Export en lot des feuilles Origin via Origin Viewer (Windows 64 bits)."""
from __future__ import annotations

import argparse
import csv
import ctypes
from ctypes import wintypes
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from origin_extract.number_text import decimal_text

import pythoncom
import win32clipboard
import win32con
import win32gui
import win32ui
from pywinauto import Application
from pywinauto.timings import Timings, TimeoutError as ViewerTimeout

Timings.window_find_timeout = 3
Timings.after_treeviewselect_wait = 0.05


class Cancelled(Exception):
    pass


class UnsupportedSheet(Exception):
    def __init__(self, message, kind='NonDataSheet'):
        super().__init__(message)
        self.kind = kind


def embedded_graph_sheet(text):
    rows = list(csv.reader(io.StringIO(text, newline=''), delimiter='\t'))
    cells = [cell.strip() for row in rows for cell in row if cell.strip()]
    return bool(cells) and all(re.fullmatch(r'embedding:[^\s\t\r\n]+', cell) for cell in cells)


@contextmanager
def viewer_lock(check, log):
    """Le presse-papiers est partagé, y compris entre deux fenêtres de l'app."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateMutexW(None, False, r'Local\OriginExtract-ViewerExport')
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    acquired = False
    waiting = False
    try:
        while True:
            check()
            status = kernel.WaitForSingleObject(handle, 100)
            if status in (0, 0x80):
                acquired = True
                break
            if status != 0x102:
                raise ctypes.WinError(ctypes.get_last_error())
            if not waiting:
                log('Une autre conversion utilise le Viewer ; mise en attente…')
                waiting = True
        yield
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


def safe_name(value: str, limit=110) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip(' .')
    if not value:
        value = 'Sans_nom'
    if re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?', value):
        value = '_' + value
    return value[:limit].rstrip(' .')


def detect_viewer() -> str:
    downloads = Path.home() / 'Downloads'
    candidates = list(downloads.glob('OriginViewer*/*.exe'))
    candidates += list(downloads.glob('OriginViewer*.exe'))
    return str(max(candidates, key=lambda p: p.stat().st_mtime)) if candidates else ''


def detect_project() -> str:
    p = Path.home() / 'Downloads' / 'from6jun2026_AGH.opju'
    return str(p) if p.exists() else ''


def click_control(ctrl, x, y):
    """Le Viewer utilise la position mémorisée par WM_MOUSEMOVE pour ses clics."""
    point = (int(y) << 16) | int(x)
    ctrl.send_message(0x200, 0, point)
    ctrl.post_message(0x201, win32con.MK_LBUTTON, point)
    ctrl.post_message(0x202, 0, point)
    time.sleep(0.035)


def tab_fingerprint(ctrl):
    """Lecture GDI du bandeau d'onglets, même derrière une autre fenêtre."""
    hwnd = ctrl.handle
    _, _, width, height = win32gui.GetClientRect(hwnd)
    if width < 60 or height < 5:
        raise RuntimeError("Le bandeau des feuilles est trop petit. Agrandissez le Viewer.")
    hdc = win32gui.GetWindowDC(hwnd)
    source = win32ui.CreateDCFromHandle(hdc)
    target = source.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    try:
        bitmap.CreateCompatibleBitmap(source, width, height)
        previous = target.SelectObject(bitmap)
        ok = ctypes.windll.user32.PrintWindow(hwnd, target.GetSafeHdc(), 1)
        if not ok:
            raise RuntimeError("Impossible de lire le bandeau des feuilles dans le Viewer.")
        bits = bitmap.GetBitmapBits(True)
        if len(set(bits)) < 2:
            raise RuntimeError("Le bandeau des feuilles n'a pas pu être dessiné.")
        target.SelectObject(previous)
        return hashlib.sha256(bits).hexdigest(), width, height
    finally:
        target.DeleteDC()
        source.DeleteDC()
        win32gui.ReleaseDC(hwnd, hdc)
        win32gui.DeleteObject(bitmap.GetHandle())


NUMBER_COMMA = re.compile(r'^[+-]?(?:\d+,\d*|,\d+)(?:[eE][+-]?\d+)?$')


def convert_table(text, decimal_point):
    # csv.reader conserve les cellules textuelles contenant des tabulations citées.
    rows = list(csv.reader(io.StringIO(text, newline=''), delimiter='\t'))
    if not rows or not any(cell.strip() for row in rows for cell in row):
        raise UnsupportedSheet("Feuille vide.")
    columns = max(map(len, rows))
    rows = [row + [''] * (columns - len(row)) for row in rows]
    if decimal_point:
        rows = [[decimal_text(v, True) for v in row] for row in rows]
    output = io.StringIO(newline='')
    csv.writer(output, delimiter='\t', lineterminator='\n').writerows(rows)
    return output.getvalue(), len(rows), columns


def column_letter(index):
    result = ''
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def load_header_overrides(project_hash):
    path = Path(__file__).resolve().with_name('noms_colonnes.json')
    if not path.exists():
        return {}
    config = json.loads(path.read_text(encoding='utf-8'))
    return config.get('projects', {}).get(project_hash, {}).get('sheets', {})


def column_headers(labels, columns, overrides=None):
    if overrides is not None and len(overrides) != columns:
        raise ValueError('La correspondance des noms ne correspond pas au nombre de colonnes.')
    metadata = []
    names = []
    used = set()
    for index in range(columns):
        values = [(row[index] if index < len(row) else '').strip() for row in labels]
        values += [''] * (3 - len(values))
        long_name, unit, comment = values[:3]
        letter = column_letter(index + 1)
        reconstructed = overrides[index] if overrides and not long_name else ''
        name = long_name or reconstructed or letter
        if unit:
            name += f' [{unit}]'
        name = re.sub(r'[\t\r\n]+', ' ', name)
        unique = name
        suffix = 2
        while unique in used:
            unique = f'{name}_{suffix}'
            suffix += 1
        used.add(unique)
        names.append(unique)
        metadata.append(dict(column=letter, name=long_name, unit=unit,
                             comment=comment, exported_header=unique,
                             reconstructed_name=reconstructed,
                             source=('Origin Long Name' if long_name else
                                     'Reconstitué par cohérence, confirmé par utilisateur' if reconstructed else
                                     'Origin column letter')))
    return names, metadata


class Exporter:
    def __init__(self, project, viewer, output, decimal_point=True, log=print, stop=None,
                 include_headers=True):
        self.project = Path(project).resolve()
        self.viewer = Path(viewer).resolve()
        self.base_output = Path(output).resolve()
        self.decimal_point = decimal_point
        self.include_headers = include_headers
        self.log = log
        self.stop = stop or threading.Event()
        self.records = []
        self.skipped = []
        self.warnings = []
        self.app = None
        self.window = None
        self.output = None
        self.last_clipboard_sequence = None
        self.header_overrides = {}

    def check(self):
        if self.stop.is_set():
            raise Cancelled("Export arrêté. Les fichiers déjà écrits sont conservés.")

    def sheet_name(self):
        self.check()
        self.window.post_message(0x111, 33999, 0)
        dialog = self.app.window(title='Save As', class_name='#32770')
        try:
            dialog.wait('visible', timeout=6)
            edits = dialog.descendants(class_name='Edit')
            edit = next((e for e in edits if e.control_id() in (1001, 1148)), None)
            if edit is None:
                raise RuntimeError("Champ de nom du fichier introuvable dans le Viewer.")
            return edit.window_text() or 'Feuille'
        finally:
            if dialog.exists(timeout=0):
                dialog.post_message(0x111, 2, 0)
                dialog.wait_not('visible', timeout=4)

    def copy_selection(self, command=32778):
        before = win32clipboard.GetClipboardSequenceNumber()
        self.window.post_message(0x111, command, 0)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            self.check()
            if win32clipboard.GetClipboardSequenceNumber() != before:
                try:
                    win32clipboard.OpenClipboard()
                    try:
                        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                            text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                            self.last_clipboard_sequence = win32clipboard.GetClipboardSequenceNumber()
                            return text
                    finally:
                        win32clipboard.CloseClipboard()
                except win32clipboard.error:
                    pass
            time.sleep(0.05)
        raise RuntimeError("La copie n'a pas renvoyé de texte. "
                           "Vérifiez que le projet autorise la copie dans Origin Viewer.")

    def grid_control(self):
        frame = self.window.child_window(class_name='GxMdiFrame').wrapper_object()
        # Des graphes intégrés contiennent leurs propres contrôles portant le
        # même identifiant. Seule la grille directement sous le classeur compte.
        grids = [item for item in frame.children() if item.class_name() == 'AfxWnd140u'
                 and item.control_id() == 59648 and item.is_visible()]
        if not grids:
            raise UnsupportedSheet("Cette feuille ne contient pas de grille de données copiable.")
        return max(grids, key=lambda item: item.rectangle().width() * item.rectangle().height())

    def copy_sheet(self):
        grid = self.grid_control()
        child_ids = {item.control_id() for item in grid.children(class_name='AfxWnd140u')}
        if {1, 2}.issubset(child_ids):
            raise UnsupportedSheet("Rapport d'analyse Origin : mise en page non exportable en tableau TXT.",
                                   'AnalysisReport')
        click_control(grid, 25, 12)  # coin supérieur gauche : toutes les cellules
        try:
            menu = win32gui.GetMenu(self.window.handle)
            if menu:
                edit = win32gui.GetSubMenu(menu, 1)
                state = win32gui.GetMenuState(edit, 32778, win32con.MF_BYCOMMAND)
                if state != -1 and state & (win32con.MF_GRAYED | win32con.MF_DISABLED):
                    raise UnsupportedSheet("La copie n'est pas disponible sur cette feuille (vide ou non tabulaire).")
            return self.copy_selection()  # Copy (full precision)
        finally:
            # Quitter tout état de sélection/drag avant de changer de classeur.
            grid.post_message(0x1f, 0, 0)

    def copy_labels(self, columns):
        grid = self.grid_control()
        try:
            # Le clic sur Long Name sélectionne les libellés. Selon l'état du
            # Viewer, la copie inclut aussi F(x) et Sparklines : seuls les trois
            # premiers niveaux (nom, unité, commentaire) nous intéressent.
            click_control(grid, 40, 47)
            text = self.copy_selection(57634)  # Copy : libellés textuels
            rows = list(csv.reader(io.StringIO(text, newline=''), delimiter='\t'))
            if not 1 <= len(rows) <= 5 or any(len(row) != columns for row in rows):
                raise RuntimeError("La copie des noms/unités/commentaires n'a pas renvoyé "
                                   f'les libellés de {columns} colonnes. Export interrompu pour éviter des noms erronés.')
            labels = rows[:3]
            if any('OLabGridClipboardImageTemp' in cell for row in labels for cell in row):
                raise RuntimeError("Le Viewer a sélectionné des images de sparklines au lieu des noms de colonnes.")
            return labels + [[''] * columns for _ in range(3 - len(labels))]
        finally:
            grid.post_message(0x1f, 0, 0)

    def export_book(self, folder, book):
        tab = self.window.child_window(class_name='AfxWnd140u', control_id=59919)
        # Revenir au début du bandeau avant de parcourir les onglets visibles.
        fp, width, height = tab_fingerprint(tab)
        for _ in range(1000):
            self.check()
            click_control(tab, 12, height // 2)
            newer, width, height = tab_fingerprint(tab)
            if newer == fp:
                break
            fp = newer
        else:
            raise RuntimeError("Impossible d'atteindre le début du bandeau des feuilles.")
        click_control(tab, 65, height // 2)
        seen_sheets = set()

        def save_current():
            self.check()
            # Le rendu des rapports Origin peut se terminer après celui de
            # l'onglet ; ne pas lire la grille de la feuille précédente.
            time.sleep(.15)
            try:
                raw = self.copy_sheet()
            except UnsupportedSheet as exc:
                try:
                    identity = self.grid_control().handle
                except UnsupportedSheet:
                    identity = tab_fingerprint(tab)[0]
                key = (identity, 'non_tabulaire')
                if key not in seen_sheets:
                    seen_sheets.add(key)
                    self.skipped.append(dict(folder='/'.join(folder), book=book['short'],
                                             type=exc.kind, reason=str(exc)))
                    self.log(f"Ignoré dans {book['short']} : {exc}")
                return
            try:
                name = self.sheet_name()
            except ViewerTimeout:
                # Les rapports peuvent exposer une copie aplatie mêlant objets,
                # statistiques et texte, sans commande d'export de feuille.
                if re.search(r'(?:^|[\t\r\n])embedding:[^\t\r\n]+', raw):
                    key = ('rapport', hashlib.sha256(raw.encode('utf-8')).hexdigest())
                    if key not in seen_sheets:
                        seen_sheets.add(key)
                        self.skipped.append(dict(folder='/'.join(folder), book=book['short'],
                            type='AnalysisReport', reason="Rapport avec objets intégrés, sans export tabulaire dans le Viewer."))
                        self.log(f"Rapport d'analyse ignoré dans {book['short']}.")
                    return
                name = f"{book['short']}_feuille_{len(seen_sheets) + 1}"
                self.warnings.append(dict(book=book['short'], sheet=name, type='SheetNameUnavailable',
                    reason='Nom de feuille non lisible dans le Viewer ; nom de fichier générique utilisé.'))
                self.log(f'Attention : nom de feuille non lisible ; {name} utilisé.')
            # Évite les doublons produits quand plusieurs points tombent sur le même onglet.
            key = (name, hashlib.sha256(raw.encode('utf-8')).hexdigest())
            if key in seen_sheets:
                return
            seen_sheets.add(key)
            if embedded_graph_sheet(raw):
                self.skipped.append(dict(folder='/'.join(folder), book=book['short'], sheet=name,
                                         type='EmbeddedGraphSheet', reason='Feuille de graphes intégrés, sans tableau de données.'))
                self.log(f'Graphes intégrés ignorés : {name}')
                return
            try:
                content, rows, columns = convert_table(raw, self.decimal_point)
            except UnsupportedSheet as exc:
                self.skipped.append(dict(folder='/'.join(folder), book=book['short'], sheet=name,
                                         type='EmptySheet', reason=str(exc)))
                self.log(f'Feuille vide ignorée : {name}')
                return
            metadata = None
            metadata_error = None
            if self.include_headers:
                try:
                    labels = self.copy_labels(columns)
                except Cancelled:
                    raise
                except RuntimeError as exc:
                    metadata_error = str(exc)
                    labels = [[''] * columns for _ in range(3)]
                    self.warnings.append(dict(book=book['short'], sheet=name, type='ColumnMetadataUnavailable',
                                              reason=metadata_error))
                    self.log(f'Attention : noms de colonnes non lisibles dans {name} ; lettres conservées.')
                headers, metadata = column_headers(labels, columns, self.header_overrides.get(book['short']))
                if metadata_error:
                    for item in metadata:
                        if not item.get('reconstructed_name'):
                            item['source'] = 'Métadonnées non lisibles ; lettre de colonne'
                heading = io.StringIO(newline='')
                csv.writer(heading, delimiter='\t', lineterminator='\n').writerow(headers)
                content = heading.getvalue() + content
            destination = self.output.joinpath(*(safe_name(v, 50) for v in folder))
            destination.mkdir(parents=True, exist_ok=True)
            stem = safe_name(name)
            path = destination / (stem + '.txt')
            index = 2
            while path.exists():
                path = destination / f'{stem}__{index}.txt'
                index += 1
            # Création exclusive : aucun export existant n'est écrasé.
            with path.open('x', encoding='utf-8', newline='') as stream:
                stream.write(content)
            self.records.append(dict(folder='/'.join(folder), book=book['short'],
                                     title=book['title'], sheet=name, rows=rows,
                                     columns=columns, file=str(path.relative_to(self.output)),
                                     column_metadata=metadata,
                                     metadata_warning=metadata_error,
                                     sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            self.write_index('en cours')
            self.log(f"{len(self.records):02d}  {name}.txt — {rows} lignes, {columns} colonnes")
            if metadata is not None and any(c.get('reconstructed_name') for c in metadata):
                self.log('    Noms reconstitués selon la correspondance confirmée.')
            elif metadata is not None and not any(c['name'] for c in metadata):
                self.log('    Lettres de colonnes conservées.' if metadata_error else
                         '    Noms absents dans Origin : lettres de colonnes conservées.')

        save_current()
        seen_views = set()
        for _ in range(1000):
            self.check()
            fp, width, height = tab_fingerprint(tab)
            if fp in seen_views:
                break
            seen_views.add(fp)
            # Chaque onglet a une largeur minimale supérieure à 12 pixels.
            # Le rendu ne change que lors d'un changement de feuille ou de défilement.
            for x in range(60, width - 2, 12):
                self.check()
                click_control(tab, x, height // 2)
                newer, _, _ = tab_fingerprint(tab)
                if newer != fp:
                    save_current()
                    newer, _, _ = tab_fingerprint(tab)
                fp = newer
            # La flèche droite fait apparaître les onglets suivants, s'il y en a.
            before, _, _ = tab_fingerprint(tab)
            click_control(tab, 39, height // 2)
            after, _, _ = tab_fingerprint(tab)
            if after == before:
                break
        else:
            raise RuntimeError("Le parcours des onglets n'a pas pu être terminé.")

    def write_index(self, status, error=None):
        info = dict(project=str(self.project), viewer=str(self.viewer), status=status,
                    format='UTF-8, tabulations, avec en-tête' if self.include_headers else 'UTF-8, tabulations, sans en-tête',
                    header_lines=1 if self.include_headers else 0,
                    decimals='point' if self.decimal_point else 'format du Viewer',
                    sheets=self.records, skipped=self.skipped, warnings=self.warnings, error=error)
        temp = self.output / '_rapport.json.tmp'
        temp.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(self.output / '_rapport.json')
        with (self.output / '_index.csv').open('w', encoding='utf-8-sig', newline='') as f:
            fields = ['folder', 'book', 'title', 'sheet', 'rows', 'columns', 'file', 'sha256']
            writer = csv.DictWriter(f, fieldnames=fields, delimiter=';')
            writer.writeheader()
            writer.writerows({key: item[key] for key in fields} for item in self.records)

    def run(self):
        with viewer_lock(self.check, self.log):
            return self._run()

    def _run(self):
        if not self.project.is_file() or self.project.suffix.lower() not in ('.opj', '.opju'):
            raise ValueError("Sélectionnez un fichier .opj ou .opju existant.")
        if not self.viewer.is_file() or self.viewer.suffix.lower() != '.exe':
            raise ValueError("Sélectionnez l'exécutable Origin Viewer.")
        before_hash = hashlib.sha256(self.project.read_bytes()).hexdigest()
        self.header_overrides = load_header_overrides(before_hash)
        self.base_output.mkdir(parents=True, exist_ok=True)
        suffix = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output = self.base_output / f'{safe_name(self.project.stem, 55)}_txt_{suffix}'
        count = 2
        while self.output.exists():
            self.output = self.base_output / f'{safe_name(self.project.stem, 55)}_txt_{suffix}_{count}'
            count += 1
        self.output.mkdir()
        self.log(f'Destination : {self.output}')
        original_clipboard = None
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    original_clipboard = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
        except win32clipboard.error:
            pass
        try:
            self.log('Ouverture du projet dans une nouvelle instance du Viewer…')
            command = subprocess.list2cmdline([str(self.viewer), str(self.project)])
            self.app = Application(backend='win32').start(command, work_dir=str(self.viewer.parent))
            # Certaines ouvertures depuis un dossier temporaire ne donnent que
            # le titre « Orgin Viewer » (orthographe du logiciel), sans chemin.
            self.window = self.app.window(title_re='.*(?:Origin|Orgin) Viewer.*', class_name='#32770')
            self.window.wait('visible', timeout=30)
            tree = self.window.child_window(class_name='SysTreeView32')
            tree.wait('exists', timeout=30)
            # Largeur suffisante pour le bandeau ; l'export utilise des messages natifs.
            self.window.restore()
            self.window.move_window(20, 20, 1400, 850)
            roots = tree.roots()
            if not roots:
                raise RuntimeError("Le Viewer n'a pas chargé l'arborescence du projet.")

            def walk(node, path):
                self.check()
                node.select()
                time.sleep(0.08)
                listing = self.window.child_window(class_name='SysListView32').wrapper_object()
                headers = [c['text'].lower() for c in listing.columns()]
                def column(name):
                    if name not in headers:
                        raise RuntimeError(f"Colonne du Viewer introuvable : {name}")
                    return headers.index(name)
                columns = [column(n) for n in ('title', 'short name', 'type')]
                books = []
                for row in range(listing.item_count()):
                    title, short, kind = [listing.get_item(row, c).text() for c in columns]
                    if kind == 'Workbook':
                        books.append(dict(row=row, title=title, short=short))
                    elif kind not in ('Folder', ''):
                        self.skipped.append(dict(folder='/'.join(path), name=short or title, type=kind))
                self.log(f"{'/'.join(path) or '/'} : {len(books)} classeur(s)")
                for book in books:
                    self.check()
                    listing.get_item(book['row']).ensure_visible()
                    rect = listing.get_item_rect(book['row'])
                    click_control(listing, 30, (rect.top + rect.bottom) // 2)
                    deadline = time.monotonic() + 6
                    def book_active():
                        if f"/{book['short']} - Origin Viewer" in self.window.window_text():
                            return True
                        return any(view.window_text() == book['short'] or
                                   view.window_text().startswith(book['short'] + ' - ')
                                   for view in self.window.descendants(class_name='_Ogn3df_'))
                    while not book_active():
                        if time.monotonic() > deadline:
                            raise RuntimeError(f"Le Viewer n'a pas activé le classeur {book['short']}.")
                        self.check()
                        time.sleep(0.05)
                    time.sleep(0.1)  # laisser le nouveau tableau terminer sa mise en page
                    self.export_book(path, book)
                for child in node.children():
                    walk(child, path + [child.text()])

            walk(roots[0], [])
            if not self.records:
                raise RuntimeError("Aucune feuille de données exportable n'a été trouvée.")
            if hashlib.sha256(self.project.read_bytes()).hexdigest() != before_hash:
                raise RuntimeError("Le fichier source a changé pendant l'export.")
            self.write_index('terminé')
            self.log(f'Terminé : {len(self.records)} fichier(s) TXT. Le projet source est intact.')
            return self.output
        except Exception as exc:
            self.write_index('arrêté' if isinstance(exc, Cancelled) else 'erreur', str(exc))
            raise
        finally:
            if self.window is not None:
                try:
                    # Fermer uniquement l'instance créée par ce programme.
                    for dialog in self.app.windows(class_name='#32770'):
                        if dialog.handle != self.window.handle:
                            dialog.post_message(0x111, 2, 0)
                    self.window.post_message(0x10, 0, 0)
                except Exception:
                    pass
            if original_clipboard is not None and self.last_clipboard_sequence is not None:
                try:
                    win32clipboard.OpenClipboard()
                    try:
                        if win32clipboard.GetClipboardSequenceNumber() == self.last_clipboard_sequence:
                            win32clipboard.EmptyClipboard()
                            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, original_clipboard)
                    finally:
                        win32clipboard.CloseClipboard()
                except win32clipboard.error:
                    pass


def gui(args):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    root = tk.Tk()
    root.title('Origin → TXT — export de toutes les feuilles')
    root.geometry('820x570')
    root.minsize(720, 500)
    frame = ttk.Frame(root, padding=18)
    frame.pack(fill='both', expand=True)
    frame.columnconfigure(1, weight=1)
    project = tk.StringVar(value=args.project or detect_project())
    viewer = tk.StringVar(value=args.viewer or detect_viewer())
    output = tk.StringVar(value=args.output or str(Path.home() / 'Downloads' / 'Exports_Origin'))
    point = tk.BooleanVar(value=not args.decimal_comma)
    include_headers = tk.BooleanVar(value=not args.no_headers)
    for row, (label, variable, kind) in enumerate([
        ('Projet Origin', project, 'project'), ('Origin Viewer', viewer, 'viewer'),
        ('Dossier des exports', output, 'output')]):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', pady=6)
        ttk.Entry(frame, textvariable=variable).grid(row=row, column=1, sticky='ew', padx=10)
        def browse(v=variable, k=kind):
            if k == 'output':
                value = filedialog.askdirectory(parent=root, initialdir=v.get())
            else:
                types = [('Projets Origin', '*.opju *.opj')] if k == 'project' else [('Origin Viewer', '*.exe')]
                value = filedialog.askopenfilename(parent=root, filetypes=types)
            if value:
                v.set(value)
        ttk.Button(frame, text='Parcourir…', command=browse).grid(row=row, column=2)
    ttk.Checkbutton(frame, text='Décimales avec un point (pratique pour Python)',
                    variable=point).grid(row=3, column=0, columnspan=3, sticky='w', pady=(10, 3))
    ttk.Checkbutton(frame, text='Inclure les noms de colonnes et les unités',
                    variable=include_headers).grid(row=4, column=0, columnspan=3, sticky='w')
    ttk.Label(frame, text='Un TXT par feuille • UTF-8 • tabulations • pleine précision du Viewer\n'
              'Pendant l’export, laissez le Viewer ouvert et évitez de copier du texte.',
              foreground='#555555').grid(row=5, column=0, columnspan=3, sticky='w', pady=8)
    messages = queue.Queue()
    stop = threading.Event()
    state = {'running': False, 'destination': None}
    buttons = ttk.Frame(frame)
    buttons.grid(row=6, column=0, columnspan=3, sticky='w', pady=8)
    progress = ttk.Progressbar(frame, mode='indeterminate')
    progress.grid(row=7, column=0, columnspan=3, sticky='ew', pady=8)
    text = tk.Text(frame, height=12, wrap='word', state='disabled', font=('Consolas', 10))
    text.grid(row=8, column=0, columnspan=3, sticky='nsew')
    frame.rowconfigure(8, weight=1)

    def run():
        state['running'] = True
        state['destination'] = None
        stop.clear()
        start.configure(state='disabled')
        cancel.configure(state='normal')
        open_button.configure(state='disabled')
        progress.start()
        parameters = (project.get(), viewer.get(), output.get(), point.get())
        with_headers = include_headers.get()
        def worker():
            pythoncom.CoInitialize()
            engine = Exporter(*parameters, log=lambda s: messages.put(('log', s)), stop=stop,
                              include_headers=with_headers)
            try:
                destination = engine.run()
                messages.put(('done', str(destination)))
            except Exception as exc:
                if engine.output:
                    (engine.output / '_erreur.log').write_text(traceback.format_exc(), encoding='utf-8')
                messages.put(('error', str(exc)))
            finally:
                pythoncom.CoUninitialize()
        threading.Thread(target=worker, daemon=True).start()

    start = ttk.Button(buttons, text='Exporter toutes les feuilles', command=run)
    start.pack(side='left')
    cancel = ttk.Button(buttons, text='Arrêter', state='disabled', command=stop.set)
    cancel.pack(side='left', padx=10)
    open_button = ttk.Button(buttons, text='Ouvrir les TXT', state='disabled',
                             command=lambda: os.startfile(state['destination']))
    open_button.pack(side='left')

    def poll():
        while True:
            try:
                kind, value = messages.get_nowait()
            except queue.Empty:
                break
            text.configure(state='normal')
            text.insert('end', value + '\n')
            text.see('end')
            text.configure(state='disabled')
            if kind in ('done', 'error'):
                state['running'] = False
                progress.stop()
                start.configure(state='normal')
                cancel.configure(state='disabled')
                if kind == 'done':
                    state['destination'] = value
                    open_button.configure(state='normal')
                    messagebox.showinfo('Export terminé', f'Toutes les feuilles parcourues ont été exportées.\n\n{value}')
                else:
                    messagebox.showerror('Export interrompu', value)
        root.after(100, poll)

    def close():
        if state['running']:
            stop.set()
            messages.put(('log', 'Arrêt demandé… Attendez la fin avant de fermer.'))
        else:
            root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    poll()
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project')
    parser.add_argument('--viewer')
    parser.add_argument('--output')
    parser.add_argument('--decimal-comma', action='store_true')
    parser.add_argument('--no-gui', action='store_true')
    parser.add_argument('--no-headers', action='store_true', help='Exporter uniquement les données, sans en-tête')
    parser.add_argument('--cancel-file', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.no_gui:
        if not all((args.project, args.viewer, args.output)):
            parser.error('--no-gui nécessite --project, --viewer et --output')
        class FileStop:
            def is_set(self):
                return bool(args.cancel_file and Path(args.cancel_file).exists())
        engine = Exporter(args.project, args.viewer, args.output, not args.decimal_comma,
                          include_headers=not args.no_headers, stop=FileStop())
        print(engine.run(), flush=True)
    else:
        gui(args)


if __name__ == '__main__':
    main()

import builtins
import copy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from origin_extract import core
from origin_extract.bridge import Bridge, convert_remote, request
from fixtures import sample_project

SAMPLE = Path(__file__).resolve().parents[1] / 'Exemples/from6jun2026_AGH.originpack'


class PortableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = core.load_pack(SAMPLE) if SAMPLE.exists() else sample_project()

    def test_sample_counts_and_reconstructed_names(self):
        self.assertEqual(len(self.project.sheets), 19)
        self.assertEqual(self.project.row_count, 37881)
        self.assertEqual(sum(s.reconstructed for s in self.project.sheets), 6)
        for sheet in self.project.sheets:
            self.assertEqual(len(sheet.headers), sheet.record['columns'])
            self.assertEqual(len(sheet.rows), sheet.record['rows'])
            self.assertEqual(core.digest(sheet.content), sheet.record['sha256'])

    def test_offline_roundtrip_without_windows_modules(self):
        original_import = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name.startswith(('win32', 'pywinauto', 'pythoncom', 'export_origin')):
                raise AssertionError('Dépendance Windows chargée dans le mode portable : ' + name)
            return original_import(name, *args, **kwargs)
        with patch('builtins.__import__', guarded), tempfile.TemporaryDirectory() as folder:
            project = core.load_pack(core.pack_bytes(self.project))
            exported = core.export_project(project, folder)
            restored = core.load_export(exported)
            packed = core.load_pack(core.pack_bytes(restored))
            self.assertEqual([s.content for s in project.sheets], [s.content for s in packed.sheets])
            self.assertEqual([s.record['column_metadata'] for s in project.sheets],
                             [s.record['column_metadata'] for s in packed.sheets])

    def test_csv_decimal_comma_and_selection(self):
        options = core.ExportOptions('csv', ';', True, False)
        with tempfile.TemporaryDirectory() as folder:
            result = core.export_project(self.project, folder, [0, 12], options)
            report = json.loads((result / '_rapport.json').read_text(encoding='utf-8'))
            self.assertEqual(len(report['sheets']), 2)
            for item in report['sheets']:
                with (result / item['file']).open(encoding='utf-8', newline='') as stream:
                    rows = list(csv.reader(stream, delimiter=';'))
                self.assertEqual(len(rows), item['rows'] + 1)
                self.assertTrue(all(len(r) == item['columns'] for r in rows))
            restored = core.load_export(result)
            self.assertEqual(restored.sheets[0].content, self.project.sheets[0].content)
            self.assertEqual(restored.sheets[1].content, self.project.sheets[12].content)

    def test_no_headers_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            one = core.export_project(self.project, folder, [0], core.ExportOptions(include_headers=False))
            two = core.export_project(self.project, folder, [0])
            self.assertNotEqual(one, two)
            report = json.loads((one / '_rapport.json').read_text(encoding='utf-8'))
            raw = (one / report['sheets'][0]['file']).read_bytes()
            self.assertEqual(raw, self.project.sheets[0].content.partition(b'\n')[2])

    def test_corrupt_pack_is_rejected(self):
        source = io.BytesIO(core.pack_bytes(self.project))
        target = io.BytesIO()
        with zipfile.ZipFile(source) as incoming, zipfile.ZipFile(target, 'w') as outgoing:
            for info in incoming.infolist():
                raw = incoming.read(info.filename)
                if info.filename == 'tables/0000.tsv':
                    raw += b'corruption'
                outgoing.writestr(info.filename, raw)
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            core.load_pack(target.getvalue())

    def test_pack_path_traversal_is_rejected(self):
        target = io.BytesIO()
        manifest = dict(format=core.PACK_FORMAT, name='test', header_lines=1,
                        sheets=[dict(file='../outside.tsv', columns=1, rows=1)])
        with zipfile.ZipFile(target, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(manifest))
            archive.writestr('../outside.tsv', 'A\n1\n')
        with self.assertRaisesRegex(ValueError, 'Chemin'):
            core.load_pack(target.getvalue())

    def test_cancel_does_not_produce_completed_export(self):
        stop = threading.Event()
        with tempfile.TemporaryDirectory() as folder:
            def progress(current, total, message):
                stop.set()
            with self.assertRaises(core.Cancelled):
                core.export_project(self.project, folder, stop=stop, progress=progress)
            self.assertFalse(list(Path(folder).glob('*/_rapport.json')))
            self.assertEqual(len(list(Path(folder).glob('*/_interrompu.txt'))), 1)

    def test_bridge_authentication_and_protocol(self):
        seen = []
        def converter(source, viewer, destination, stop, log):
            seen.append(source.read_bytes())
            log('Conversion de test')
            return self.project
        service = Bridge('unused', converter=converter)
        service.start()
        try:
            base = f'http://127.0.0.1:{service.port}'
            with self.assertRaisesRegex(RuntimeError, 'Clé'):
                request(base, 'incorrect', '/health')
            with tempfile.TemporaryDirectory() as folder:
                source = Path(folder) / 'test.opju'
                source.write_bytes(b'CPYUA test-only')
                result = convert_remote(source, base, service.token)
            self.assertEqual(seen, [b'CPYUA test-only'])
            self.assertEqual([s.content for s in result.sheets], [s.content for s in self.project.sheets])
        finally:
            service.close()


if __name__ == '__main__':
    unittest.main()

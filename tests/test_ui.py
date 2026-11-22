import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from origin_extract.core import load_pack
from origin_extract.bridge import Bridge
from origin_extract.ui import Window, STYLE
from fixtures import sample_project

SAMPLE = Path(__file__).resolve().parents[1] / 'Exemples/from6jun2026_AGH.originpack'


class Settings:
    def __init__(self, values):
        self.values = values
    def value(self, key, default=None):
        return self.values.get(key, default)
    def setValue(self, key, value):
        self.values[key] = value


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')
        cls.app.setStyleSheet(STYLE)
        cls.project = load_pack(SAMPLE) if SAMPLE.exists() else sample_project()

    def test_preview_selection_search_and_provenance(self):
        window = Window()
        try:
            window.set_project(self.project)
            self.assertEqual(len(window.checked()), 19)
            window.show()
            self.app.processEvents()
            rect = window.list.visualItemRect(window.list.item(0))
            point = rect.center()
            point.setX(rect.left() + 14)
            QTest.mouseClick(window.list.viewport(), Qt.MouseButton.LeftButton, pos=point)
            self.assertEqual(window.list.item(0).checkState(), Qt.CheckState.Unchecked)
            window.search.setText('sr3ru2o7sust')
            self.assertEqual(sum(not window.list.item(i).isHidden() for i in range(19)), 7)
            self.assertEqual(len(window.checked()), 18)
            window.list.setCurrentRow(12)
            self.assertEqual(window.table.model().rowCount(), 122)
            self.assertEqual(window.provenance.text(), 'Reconstitué')
            self.assertEqual(window.table.model().headerData(0, Qt.Orientation.Horizontal), 'Tsample')
            self.assertFalse(window.plot.grab().isNull())
            from dataclasses import replace
            window.set_project(replace(self.project, sheets=self.project.sheets[:2]))
            self.assertEqual(window.list.count(), 2)
            self.assertEqual(window.search.text(), '')
            self.assertEqual(len(window.checked()), 2)
        finally:
            window.close()

    def test_mac_interface_uses_remote_conversion(self):
        service = Bridge('unused', converter=lambda *args: self.project)
        service.start()
        window = Window()
        errors = []
        window.on_error = errors.append
        window.settings = Settings({'remote/address': f'http://127.0.0.1:{service.port}',
                                    'remote/token': service.token})
        try:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'projet.opju'
                path.write_bytes(b'CPYUA test-protocol')
                with patch('origin_extract.ui.sys.platform', 'darwin'), patch(
                        'origin_extract.ui.convert_windows', side_effect=AssertionError('Moteur Windows appelé sur Mac')):
                    window.open_path(path)
                    deadline = time.monotonic() + 10
                    while (window.project is None or window.busy()) and not errors and time.monotonic() < deadline:
                        self.app.processEvents()
                        QTest.qWait(20)
                    self.app.processEvents()
                    self.assertFalse(errors, errors)
                    self.assertIsNotNone(window.project)
                    self.assertEqual(window.project.row_count, 37881)
                    self.assertEqual(len(window.checked()), 19)
        finally:
            if window.busy():
                window.task.stop.set()
                window.task.wait(10000)
            window.close()
            service.close()


if __name__ == '__main__':
    unittest.main()

from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
import sys
import tempfile
import threading

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSettings, QThread, QTimer, Signal, QSize, QEvent
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontMetrics, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtCore import QUrl, QRectF, QLineF
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy,
    QSplitter, QStackedWidget, QTabWidget, QTableView, QVBoxLayout, QWidget, QMenu, QStyledItemDelegate, QStyle,
)

from . import __version__, __author__
from .theme import STYLE as COMPACT_STYLE, PURPLE, apply_appearance, load_fonts
from .core import Cancelled, ExportOptions, Project, convert_windows, export_project, load_export, load_pack, write_pack
from .bridge import Bridge, convert_remote, local_addresses, request

ROOT = Path(__file__).resolve().parents[1]
BLUE = PURPLE


STYLE = '''
QWidget { font-family: "Inter", "Segoe UI", ".AppleSystemUIFont", sans-serif; font-size: 13px; color: #253049; }
QMainWindow, QWidget#Shell { background: #f5f6fa; }
QFrame#Sidebar { background: #171e32; border: none; }
QLabel#Brand { color: #ffffff; font-size: 22px; font-weight: 700; }
QLabel#SideCaption { color: #8f9ab6; font-size: 11px; letter-spacing: 2px; }
QLabel#SideSmall { color: #9ca8c5; font-size: 12px; }
QLabel#SideTitle { color: #e0e6f5; font-size: 14px; font-weight: 600; }
QPushButton#SideButton { background: transparent; color: #b6c0d8; text-align: left; border: none; border-radius: 10px; padding: 13px 16px; }
QPushButton#SideButton:hover { background: #242e49; color: white; }
QPushButton#SideActive { background: #2a365b; color: #e5eaff; text-align: left; border: none; border-radius: 10px; padding: 13px 16px; font-weight: 600; }
QLabel#Title { font-size: 28px; font-weight: 700; color: #192239; }
QLabel#Subtitle { color: #828b9e; font-size: 13px; }
QLabel#Eyebrow { font-size: 11px; color: #7d88a1; font-weight: 600; letter-spacing: 2px; }
QLabel#SectionTitle { font-size: 16px; font-weight: 600; color: #23304b; }
QLabel#MetricValue { font-size: 27px; font-weight: 700; color: #243251; }
QLabel#MetricLabel { font-size: 12px; color: #828b9e; }
QLabel#FileTitle { font-size: 16px; font-weight: 600; color: #263252; }
QLabel#Body { color: #73809a; line-height: 140%; }
QLabel#Badge { background: #e9f5ef; color: #2c8164; border-radius: 10px; padding: 5px 11px; font-size: 11px; font-weight: 600; }
QLabel#Reconstructed { background: #fff3da; color: #94711b; border-radius: 9px; padding: 5px 10px; font-size: 11px; }
QLabel#BlueBadge { background: #edf0ff; color: #556cc7; border-radius: 10px; padding: 5px 11px; font-size: 11px; }
QFrame#Card, QWidget#Card { background: white; border: 1px solid #e6e9f1; border-radius: 14px; }
QFrame#Metric { background: white; border: 1px solid #e6e9f1; border-radius: 12px; }
QFrame#Hero { background: #edf0ff; border: 1px solid #dce3ff; border-radius: 18px; }
QLabel#HeroTitle { font-size: 36px; color: #243668; font-weight: 700; }
QPushButton { background: white; border: 1px solid #dfe4ee; border-radius: 9px; padding: 10px 15px; font-weight: 500; }
QPushButton:hover { background: #f2f4fc; border-color: #bdc8eb; }
QPushButton:pressed { background: #e9edfa; }
QPushButton:disabled { color: #acb3c2; background: #f1f3f7; border-color: #e4e8ef; }
QPushButton#Primary { background: #4968ed; color: white; border: none; font-weight: 600; padding: 12px 20px; }
QPushButton#Primary:hover { background: #3b59db; }
QPushButton#Primary:disabled { background: #b8c3f2; }
QPushButton#TextButton { color: #526ad4; border: none; background: transparent; padding: 4px 6px; }
QPushButton#TextButton:hover { background: #edf1ff; }
QLineEdit, QComboBox { background: white; border: 1px solid #e0e5ef; border-radius: 8px; padding: 8px 10px; min-height: 19px; selection-background-color: #4968ed; }
QLineEdit:focus, QComboBox:focus { border-color: #6e87f0; }
QComboBox::drop-down { border: none; width: 24px; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #cbd3e5; border-radius: 4px; background: white; }
QCheckBox::indicator:checked { background: #4968ed; border-color: #4968ed; image: none; }
QListWidget { background: white; border: none; outline: none; padding: 0px; }
QListWidget::item { border: 1px solid transparent; border-radius: 9px; margin: 3px 0px; padding: 6px; }
QListWidget::item:selected { background: #edf1ff; border-color: #d6e0ff; color: #304eac; }
QListWidget::item:hover { background: #f5f7fc; }
QListWidget::indicator { width: 15px; height: 15px; }
QTabWidget::pane { border: none; background: white; }
QTabBar::tab { background: transparent; color: #8b95aa; border-bottom: 2px solid transparent; padding: 12px 18px; margin-right: 6px; }
QTabBar::tab:selected { color: #4968ed; border-bottom: 2px solid #4968ed; font-weight: 600; }
QTableView { border: none; background: white; alternate-background-color: #fafbfe; gridline-color: #f0f2f7; selection-background-color: #e8edff; selection-color: #2d447f; }
QHeaderView::section { background: #f6f8fc; color: #6a7792; padding: 10px 12px; border: none; border-bottom: 1px solid #e9edf5; font-size: 11px; font-weight: 600; }
QTableCornerButton::section { background: #f6f8fc; border: none; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: #d8deeb; border-radius: 3px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { background: transparent; height: 9px; }
QScrollBar::handle:horizontal { background: #d8deeb; border-radius: 3px; min-width: 24px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QProgressBar { border: none; background: #e6eaf6; border-radius: 3px; min-height: 5px; max-height: 5px; }
QProgressBar::chunk { background: #4968ed; border-radius: 3px; }
QPlainTextEdit { background: #f4f6fb; border: 1px solid #e6eaf2; border-radius: 9px; padding: 8px; font-family: "Consolas", "Menlo", monospace; font-size: 11px; color: #71809a; }
QDialog { background: #f6f7fb; }
QToolTip { background: #202a43; color: white; border: none; padding: 7px; }
'''


STYLE = COMPACT_STYLE


def label(text='', name=None, wrap=False):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget


def button(text, callback=None, name=None):
    widget = QPushButton(text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if name:
        widget.setObjectName(name)
    if callback:
        widget.clicked.connect(callback)
    return widget


def card(layout=QVBoxLayout, name='Card', margin=18):
    widget = QFrame()
    widget.setObjectName(name)
    inner = layout(widget)
    inner.setContentsMargins(margin, margin, margin, margin)
    inner.setSpacing(12)
    return widget, inner


def app_icon(size=64):
    image = QPixmap(size, size)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 64, size / 64)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(BLUE))
    painter.drawRoundedRect(QRectF(1, 1, 62, 62), 17, 17)
    painter.setPen(QPen(QColor('white'), 3))
    painter.drawRoundedRect(QRectF(17, 17, 30, 30), 3, 3)
    painter.drawLine(17, 27, 47, 27)
    painter.drawLine(27, 17, 27, 47)
    painter.setPen(QPen(QColor('#b6c6ff'), 3))
    painter.drawLine(32, 38, 43, 38)
    painter.end()
    return QIcon(image)


class Task(QThread):
    message = Signal(str)
    progress = Signal(int, int, str)
    success = Signal(object)
    failure = Signal(str)
    stopped = Signal()

    def __init__(self, function):
        super().__init__()
        self.function = function
        self.stop = threading.Event()

    def run(self):
        try:
            result = self.function(self)
            if self.stop.is_set():
                self.stopped.emit()
            else:
                self.success.emit(result)
        except Exception as exc:
            if self.stop.is_set() or isinstance(exc, Cancelled):
                self.stopped.emit()
            else:
                self.failure.emit(str(exc))


class TableModel(QAbstractTableModel):
    def __init__(self, sheet=None):
        super().__init__()
        self.sheet = sheet

    def rowCount(self, parent=QModelIndex()):
        return min(len(self.sheet.rows), 1000) if self.sheet and not parent.isValid() else 0

    def columnCount(self, parent=QModelIndex()):
        return len(self.sheet.headers) if self.sheet and not parent.isValid() else 0

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self.sheet is None:
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            value = self.sheet.rows[index.row()][index.column()]
            if role == Qt.ItemDataRole.DisplayRole and len(value) > 13:
                try:
                    number = float(value)
                    if math.isfinite(number):
                        return f'{number:.4e}' if 0 < abs(number) < .001 else f'{number:.7g}'
                except ValueError:
                    pass
            return value
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return self.sheet.headers[section] if orientation == Qt.Orientation.Horizontal else str(section + 1)
        if role == Qt.ItemDataRole.ToolTipRole and orientation == Qt.Orientation.Horizontal:
            metadata = self.sheet.record.get('column_metadata') or []
            if section < len(metadata):
                item = metadata[section]
                return '\n'.join(filter(None, [self.sheet.headers[section], item.get('source'), item.get('comment')]))
        return None


class Plot(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(240)
        self.points = []
        self.axes = ('', '')

    def set_data(self, sheet, x, y):
        points = []
        for row in sheet.rows:
            try:
                values = float(row[x]), float(row[y])
                if all(math.isfinite(v) for v in values):
                    points.append(values)
                else:
                    points.append(None)
            except (ValueError, TypeError):
                points.append(None)
        self.points = points
        self.axes = (sheet.headers[x], sheet.headers[y])
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor('#15121b'))
        points = [p for p in self.points if p is not None]
        if len(points) < 2:
            painter.setPen(QColor('#8995ab'))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'Choisir deux colonnes numériques')
            return
        x0, x1 = min(p[0] for p in points), max(p[0] for p in points)
        y0, y1 = min(p[1] for p in points), max(p[1] for p in points)
        dx = x1 - x0 or max(abs(x0) * .01, 1)
        dy = y1 - y0 or max(abs(y0) * .01, 1)
        rect = QRectF(104, 24, max(1, self.width() - 130), max(1, self.height() - 88))
        painter.setFont(QFont('Nunito', 8))
        for i in range(5):
            yy = rect.top() + rect.height() * i / 4
            painter.setPen(QPen(QColor('#30233b'), 1))
            painter.drawLine(QLineF(rect.left(), yy, rect.right(), yy))
            painter.setPen(QColor('#9e88ad'))
            painter.drawText(QRectF(26, yy - 10, 64, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f'{y1 - dy * i / 4:.4g}')
        for i in range(3):
            xx = rect.left() + rect.width() * i / 2
            painter.setPen(QColor('#9e88ad'))
            painter.drawText(QRectF(xx - 45, rect.bottom() + 10, 90, 22), Qt.AlignmentFlag.AlignCenter, f'{x0 + dx * i / 2:.4g}')
        path = QPainterPath()
        connected = False
        stride = max(1, math.ceil(len(self.points) / 3000))
        for index, point in enumerate(self.points):
            if point is None:
                connected = False
                continue
            if index % stride and index != len(self.points) - 1:
                continue
            x, y = point
            px = rect.left() + (x - x0) / dx * rect.width()
            py = rect.bottom() - (y - y0) / dy * rect.height()
            if not connected:
                path.moveTo(px, py)
                connected = True
            else:
                path.lineTo(px, py)
        painter.setPen(QPen(QColor(BLUE), 2))
        painter.drawPath(path)
        painter.setPen(QColor('#ac92c2'))
        painter.drawText(QRectF(rect.left(), self.height() - 28, rect.width(), 20), Qt.AlignmentFlag.AlignCenter, self.axes[0])
        painter.save()
        painter.translate(15, rect.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-rect.height() / 2, -10, rect.height(), 20), Qt.AlignmentFlag.AlignCenter, self.axes[1])
        painter.restore()


class ConnectionDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle('Mac ↔ PC')
        self.resize(460, 410)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.addWidget(label('Mac ↔ PC', 'Title'))
        layout.addWidget(label('.originpack : hors ligne   ·   .opju : via le PC', 'Body'))
        tabs = QTabWidget()
        layout.addWidget(tabs)
        client = QWidget()
        form = QVBoxLayout(client)
        self.address = QLineEdit(window.settings.value('remote/address', ''))
        self.address.setPlaceholderText('http://192.168.1.10:8765')
        self.token = QLineEdit(window.settings.value('remote/token', ''))
        self.token.setPlaceholderText('Clé de connexion fournie par le PC')
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        form.addWidget(label('Adresse du PC'))
        form.addWidget(self.address)
        form.addWidget(label('Clé de connexion'))
        form.addWidget(self.token)
        self.test_status = label('', 'Body', True)
        self.test_button = button('Tester la connexion', self.test)
        form.addWidget(self.test_button)
        form.addWidget(self.test_status)
        form.addStretch()
        tabs.addTab(client, 'Mon Mac')
        server = QWidget()
        server_layout = QVBoxLayout(server)
        if sys.platform == 'win32':
            viewer_row = QHBoxLayout()
            self.viewer = QLineEdit(window.viewer_path())
            viewer_row.addWidget(self.viewer)
            viewer_row.addWidget(button('Choisir…', self.choose_viewer))
            server_layout.addWidget(label('Origin Viewer'))
            server_layout.addLayout(viewer_row)
            self.server_button = button('', self.toggle_bridge, 'Primary')
            server_layout.addWidget(self.server_button)
            self.server_address = QLineEdit()
            self.server_address.setReadOnly(True)
            self.server_token = QLineEdit()
            self.server_token.setReadOnly(True)
            self.server_token.setEchoMode(QLineEdit.EchoMode.Password)
            server_layout.addWidget(label('Adresse du PC'))
            server_layout.addWidget(self.server_address)
            server_layout.addWidget(label('Clé de connexion'))
            key_row = QHBoxLayout()
            key_row.addWidget(self.server_token)
            key_row.addWidget(button('Copier la clé', lambda: QApplication.clipboard().setText(self.server_token.text())))
            server_layout.addLayout(key_row)
            self.refresh_bridge()
        else:
            server_layout.addWidget(label('Le relais démarre sur le PC Windows.', 'SectionTitle'))
            server_layout.addWidget(label('Sur le PC : ouvrez Origin Extract, puis Connexion Mac et PC → Relais Windows. Le Mac fonctionne ensuite sans installer Origin Viewer.', 'Body', True))
        server_layout.addStretch()
        tabs.addTab(server, 'Mon PC Windows')
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.button(QDialogButtonBox.StandardButton.Save).setText('Enregistrer')
        controls.button(QDialogButtonBox.StandardButton.Cancel).setText('Fermer')
        controls.accepted.connect(self.save)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)
        self.test_task = None

    def choose_viewer(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choisir Origin Viewer', self.viewer.text(), 'Origin Viewer (*.exe)')
        if path:
            self.viewer.setText(path)

    def toggle_bridge(self):
        if self.window.bridge is not None:
            bridge = self.window.bridge
            with bridge.lock:
                busy = any(j.state in ('en_attente', 'conversion') for j in bridge.jobs.values())
            if busy:
                QMessageBox.information(self, 'Conversion en cours', 'Attendez la fin de la conversion avant de fermer le relais.')
                return
            bridge.close()
            self.window.bridge = None
        else:
            viewer = Path(self.viewer.text())
            if not viewer.is_file():
                QMessageBox.warning(self, 'Origin Viewer introuvable', 'Choisissez un exécutable Origin Viewer valide.')
                return
            try:
                secret = self.window.settings.value('relay/token', None)
                bridge = Bridge(viewer, host='0.0.0.0', port=8765, token=secret)
                bridge.start()
                self.window.bridge = bridge
                self.window.settings.setValue('relay/token', bridge.token)
                self.window.settings.setValue('viewer', str(viewer))
            except OSError as exc:
                QMessageBox.warning(self, 'Relais indisponible', str(exc))
        self.refresh_bridge()

    def refresh_bridge(self):
        bridge = self.window.bridge
        self.server_button.setText('Arrêter le relais' if bridge else 'Démarrer le relais sur ce PC')
        self.server_address.setText('  ou  '.join(local_addresses(bridge.port)) if bridge else '')
        self.server_token.setText(bridge.token if bridge else '')
        self.window.mode_label.setText('Relais Mac actif' if bridge else self.window.default_mode())

    def test(self):
        address, token = self.address.text().strip(), self.token.text().strip()
        if not address or not token:
            self.test_status.setText('Renseignez l’adresse et la clé du PC Windows.')
            return
        self.test_button.setEnabled(False)
        self.test_status.setText('Connexion au PC…')
        self.test_task = Task(lambda task: request(address, token, '/health', timeout=5))
        self.test_task.success.connect(lambda result: self.test_status.setText('PC connecté · prêt à convertir' if result.get('service') == 'origin-extract' else 'Ce service n’est pas un relais Origin Extract.'))
        self.test_task.failure.connect(self.test_status.setText)
        self.test_task.finished.connect(lambda: self.test_button.setEnabled(True))
        self.test_task.start()

    def save(self):
        self.window.settings.setValue('remote/address', self.address.text().strip())
        self.window.settings.setValue('remote/token', self.token.text().strip())
        if sys.platform == 'win32':
            self.window.settings.setValue('viewer', self.viewer.text().strip())
        self.accept()

    def done(self, result):
        if self.test_task is not None and self.test_task.isRunning():
            self.test_status.setText('Attendez la fin du test de connexion…')
            return
        super().done(result)


class LegacyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings('OriginExtract', 'OriginExtract')
        self.project = None
        self.task = None
        self.bridge = None
        self.last_output = None
        self.setWindowTitle('Origin Extract')
        self.setWindowIcon(app_icon())
        self.resize(1340, 880)
        self.setMinimumSize(1040, 660)
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(1340, available.width() - 50), min(880, available.height() - 50))
        self.setAcceptDrops(True)
        shell = QWidget()
        shell.setObjectName('Shell')
        self.setCentralWidget(shell)
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName('Sidebar')
        sidebar.setFixedWidth(214)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(20, 30, 20, 24)
        brand_row = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(38, 38))
        brand_row.addWidget(logo)
        brand_row.addWidget(label('Origin\nExtract', 'Brand'))
        side.addLayout(brand_row)
        side.addSpacing(36)
        side.addWidget(label('VOTRE ESPACE', 'SideCaption'))
        side.addSpacing(9)
        side.addWidget(button('▦   Mes tableaux', lambda: self.pages.setCurrentIndex(1 if self.project else 0), 'SideActive'))
        side.addWidget(button('↗   Connexion Mac et PC', self.connection, 'SideButton'))
        side.addWidget(button('?   Guide rapide', self.help, 'SideButton'))
        side.addStretch()
        side.addWidget(label('Le bon format.\nSur le bon ordinateur.', 'SideTitle'))
        side.addSpacing(9)
        self.mode_label = label(self.default_mode(), 'SideSmall', True)
        side.addWidget(self.mode_label)
        side.addSpacing(20)
        side.addWidget(label(f'ORIGIN EXTRACT  /  {__version__}', 'SideCaption'))
        root.addWidget(sidebar)
        main = QVBoxLayout()
        main.setContentsMargins(24, 20, 24, 16)
        main.setSpacing(12)
        root.addLayout(main, 1)
        top = QHBoxLayout()
        title_column = QVBoxLayout()
        title_column.setSpacing(5)
        title_column.addWidget(label('Du projet aux données.', 'Title'))
        title_column.addWidget(label('Prévisualisez. Choisissez. Exportez.', 'Subtitle'))
        top.addLayout(title_column)
        top.addStretch()
        self.open_button = button('＋  Ouvrir un projet', self.choose_project)
        top.addWidget(self.open_button)
        main.addLayout(top)
        self.pages = QStackedWidget()
        main.addWidget(self.pages, 1)
        self.pages.addWidget(self.build_empty())
        self.pages.addWidget(self.build_workspace())
        self.activity, activity_layout = card(QVBoxLayout, margin=12)
        self.activity.hide()
        line = QHBoxLayout()
        self.activity_label = label('', 'Body')
        line.addWidget(self.activity_label, 1)
        self.cancel_button = button('Arrêter', self.cancel_task, 'TextButton')
        line.addWidget(self.cancel_button)
        activity_layout.addLayout(line)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        activity_layout.addWidget(self.progress)
        main.addWidget(self.activity)
        bottom = QHBoxLayout()
        self.status_label = label('Prêt · glissez un projet dans la fenêtre', 'Subtitle')
        bottom.addWidget(self.status_label, 1)
        bottom.addWidget(button('Journal', self.toggle_log, 'TextButton'))
        main.addLayout(bottom)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setMaximumHeight(120)
        self.log.hide()
        main.addWidget(self.log)
        self.update_compact()

    def default_mode(self):
        return 'Windows · conversion locale' if sys.platform == 'win32' else 'Mac · prêt pour les projets portables'

    def viewer_path(self):
        stored = self.settings.value('viewer', '')
        if stored and Path(stored).is_file():
            return stored
        if sys.platform == 'win32':
            candidates = list((Path.home() / 'Downloads').glob('OriginViewer*/*.exe'))
            if candidates:
                return str(max(candidates, key=lambda p: p.stat().st_mtime))
        return ''

    def build_empty(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        hero, body = card(QVBoxLayout, 'Hero', 42)
        body.addWidget(label('VOS MESURES, À PORTÉE DE MAIN', 'Eyebrow'))
        body.addWidget(label('Un projet.\nTous ses tableaux.', 'HeroTitle'))
        body.addWidget(label('Retrouvez les noms de colonnes, vérifiez vos données et exportez\ntoutes les feuilles en une seule fois. Sur Windows et sur Mac.', 'Body', True))
        row = QHBoxLayout()
        row.addWidget(button('Ouvrir un projet', self.choose_project, 'Primary'))
        row.addWidget(button('Ouvrir un dossier d’exports', self.choose_folder))
        row.addStretch()
        body.addSpacing(12)
        body.addLayout(row)
        body.addSpacing(8)
        body.addWidget(label('Glissez ici un .opju, un .originpack ou un dossier d’exports.', 'Subtitle'))
        layout.addWidget(hero)
        sample = ROOT / 'Exemples/from6jun2026_AGH.originpack'
        if sample.exists():
            row = QHBoxLayout()
            row.addWidget(label('Votre projet Sr327 est déjà prêt pour Mac.', 'Body'))
            row.addWidget(button('Ouvrir les 19 tableaux  ↗', lambda: self.open_path(sample), 'TextButton'))
            row.addStretch()
            layout.addLayout(row)
        layout.addStretch(1)
        return page

    def build_workspace(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        source, source_layout = card(QHBoxLayout, margin=12)
        col = QVBoxLayout()
        col.setSpacing(4)
        self.project_title = label('', 'FileTitle')
        col.addWidget(self.project_title)
        self.project_detail = label('', 'Subtitle')
        col.addWidget(self.project_detail)
        source_layout.addLayout(col, 1)
        source_layout.addWidget(label('Vérifié · SHA256', 'Badge'))
        self.pack_button = button('Créer un projet pour Mac  ↗', self.save_pack)
        source_layout.addWidget(self.pack_button)
        layout.addWidget(source)
        self.metrics_widget = QWidget()
        metrics = QHBoxLayout(self.metrics_widget)
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setSpacing(13)
        self.metrics = []
        for caption in ('tableaux disponibles', 'lignes de données', 'feuilles aux noms reconstitués'):
            widget, column = card(QVBoxLayout, 'Metric', 16)
            column.setSpacing(4)
            value = label('—', 'MetricValue')
            column.addWidget(value)
            column.addWidget(label(caption, 'MetricLabel'))
            self.metrics.append(value)
            metrics.addWidget(widget, 1)
        layout.addWidget(self.metrics_widget)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(14)
        collection, left = card(QVBoxLayout, margin=12)
        left.setSpacing(8)
        heading = QHBoxLayout()
        heading.addWidget(label('Vos tableaux', 'SectionTitle'))
        heading.addStretch()
        heading.addWidget(button('Tout / Aucun', self.toggle_selection, 'TextButton'))
        left.addLayout(heading)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Rechercher une feuille…')
        self.search.textChanged.connect(self.filter_sheets)
        left.addWidget(self.search)
        self.list = QListWidget()
        self.list.setMinimumHeight(130)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setSpacing(0)
        self.list.currentRowChanged.connect(self.select_sheet)
        self.list.itemChanged.connect(self.update_selection)
        left.addWidget(self.list, 1)
        self.selection_label = label('', 'Subtitle')
        left.addWidget(self.selection_label)
        split.addWidget(collection)
        preview, right = card(QVBoxLayout, margin=12)
        right.setSpacing(8)
        self.sheet_title = label('', 'SectionTitle')
        self.sheet_title.setWordWrap(True)
        self.sheet_title.setMaximumHeight(48)
        right.addWidget(self.sheet_title)
        detail = QHBoxLayout()
        self.sheet_detail = label('', 'Subtitle')
        detail.addWidget(self.sheet_detail, 1)
        self.provenance = label('', 'BlueBadge')
        detail.addWidget(self.provenance)
        right.addLayout(detail)
        tabs = QTabWidget()
        self.table = QTableView()
        self.table.setMinimumHeight(125)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setDefaultSectionSize(112)
        self.table.verticalHeader().setDefaultSectionSize(35)
        tabs.addTab(self.table, 'Données')
        graph = QWidget()
        graph_layout = QVBoxLayout(graph)
        axes = QHBoxLayout()
        axes.addWidget(label('X', 'Subtitle'))
        self.x_axis = QComboBox()
        axes.addWidget(self.x_axis, 1)
        axes.addWidget(label('Y', 'Subtitle'))
        self.y_axis = QComboBox()
        axes.addWidget(self.y_axis, 1)
        self.x_axis.currentIndexChanged.connect(self.update_plot)
        self.y_axis.currentIndexChanged.connect(self.update_plot)
        graph_layout.addLayout(axes)
        self.plot = Plot()
        graph_layout.addWidget(self.plot, 1)
        graph_layout.addWidget(label('Aperçu échantillonné si nécessaire · aucun ajustement', 'Subtitle'))
        tabs.addTab(graph, 'Courbe')
        right.addWidget(tabs, 1)
        self.preview_note = label('Aperçu des 1 000 premières lignes. Toutes les lignes sont exportées.', 'Subtitle')
        self.preview_note.setWordWrap(True)
        right.addWidget(self.preview_note)
        split.addWidget(preview)
        split.setSizes([330, 650])
        layout.addWidget(split, 1)
        footer, foot = card(QVBoxLayout, margin=12)
        self.options_bar = QWidget()
        options = QHBoxLayout(self.options_bar)
        options.setContentsMargins(0, 0, 0, 0)
        options.addWidget(label('EXPORT', 'Eyebrow'))
        self.extension = QComboBox()
        self.extension.addItems(['TXT', 'CSV'])
        self.extension.setMinimumWidth(76)
        options.addWidget(self.extension)
        self.separator = QComboBox()
        self.separator.addItem('Tabulations', '\t')
        self.separator.addItem('Point-virgule', ';')
        self.separator.addItem('Virgule', ',')
        options.addWidget(self.separator)
        self.headers = QCheckBox('En-têtes inclus')
        self.headers.setChecked(True)
        options.addWidget(self.headers)
        self.decimals = QCheckBox('Décimales : point')
        self.decimals.setChecked(True)
        options.addWidget(self.decimals)
        options.addStretch()
        foot.addWidget(self.options_bar)
        target = QHBoxLayout()
        self.options_button = button('Réglages · TXT', self.export_settings, 'TextButton')
        target.addWidget(self.options_button)
        self.destination = QLineEdit(self.settings.value('output', str(Path.home() / 'Downloads/Exports_Origin')))
        self.destination.setReadOnly(True)
        target.addWidget(self.destination, 1)
        target.addWidget(button('Choisir…', self.choose_output))
        self.export_button = button('Exporter les tableaux  ↗', self.export, 'Primary')
        target.addWidget(self.export_button)
        foot.addLayout(target)
        layout.addWidget(footer)
        return page

    def update_compact(self):
        if not hasattr(self, 'metrics_widget'):
            return
        compact = self.height() < 820
        self.metrics_widget.setVisible(not compact)
        self.options_bar.setVisible(not compact)
        self.options_button.setVisible(compact)
        if self.project is not None:
            project = self.project
            self.project_detail.setText(
                f'{len(project.sheets)} tableaux · {project.row_count:,} lignes · '
                f'{sum(s.reconstructed for s in project.sheets)} feuilles aux noms reconstitués'.replace(',', ' ')
                if compact else 'Projet portable · disponible hors ligne · valeurs et en-têtes conservés')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_compact()

    def export_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Réglages de l’export')
        dialog.setMinimumWidth(390)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(label('Vos données, au bon format.', 'SectionTitle'))
        extension, separator = QComboBox(), QComboBox()
        extension.addItems(['TXT', 'CSV'])
        extension.setCurrentIndex(self.extension.currentIndex())
        separator.addItems(['Tabulations', 'Point-virgule', 'Virgule'])
        separator.setCurrentIndex(self.separator.currentIndex())
        headers = QCheckBox('Inclure les noms de colonnes')
        headers.setChecked(self.headers.isChecked())
        decimals = QCheckBox('Utiliser un point décimal')
        decimals.setChecked(self.decimals.isChecked())
        layout.addWidget(label('Format'))
        layout.addWidget(extension)
        layout.addWidget(label('Séparateur'))
        layout.addWidget(separator)
        layout.addWidget(headers)
        layout.addWidget(decimals)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(dialog.accept)
        controls.rejected.connect(dialog.reject)
        layout.addWidget(controls)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.extension.setCurrentIndex(extension.currentIndex())
            self.separator.setCurrentIndex(separator.currentIndex())
            self.headers.setChecked(headers.isChecked())
            self.decimals.setChecked(decimals.isChecked())
            self.options_button.setText(f'Réglages · {extension.currentText()}')

    def filter_sheets(self, text):
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(text.casefold() not in self.project.sheets[i].name.casefold())

    def checked(self):
        return [i for i in range(self.list.count()) if self.list.item(i).checkState() == Qt.CheckState.Checked]

    def toggle_selection(self):
        state = Qt.CheckState.Unchecked if len(self.checked()) == self.list.count() else Qt.CheckState.Checked
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(state)
        self.list.blockSignals(False)
        self.update_selection()

    def update_selection(self):
        selected = len(self.checked())
        self.selection_label.setText(f'{selected} / {self.list.count()} sélectionnés')
        self.export_button.setText(f'Exporter {selected} tableau{"x" if selected != 1 else ""}  ↗')
        self.export_button.setEnabled(bool(selected) and not self.busy())

    def busy(self):
        return self.task is not None and self.task.isRunning()

    def start_task(self, function, title, success):
        if self.busy():
            return
        self.task = Task(function)
        self.activity.show()
        self.activity_label.setText(title)
        self.progress.setRange(0, 0)
        self.cancel_button.setEnabled(True)
        self.open_button.setEnabled(False)
        self.pack_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.task.message.connect(self.on_log)
        self.task.progress.connect(self.on_progress)
        self.task.success.connect(success)
        self.task.failure.connect(self.on_error)
        self.task.stopped.connect(lambda: self.status_label.setText('Opération arrêtée.'))
        self.task.finished.connect(self.finish_task)
        self.task.start()

    def on_log(self, message):
        self.log.appendPlainText(message)
        self.activity_label.setText(message)

    def on_progress(self, current, total, message):
        self.progress.setRange(0, total)
        self.progress.setValue(current)
        self.activity_label.setText(f'{current} / {total} · {message}')

    def finish_task(self):
        self.activity.hide()
        self.open_button.setEnabled(True)
        self.pack_button.setEnabled(self.project is not None)
        self.update_selection()

    def cancel_task(self):
        if self.busy():
            self.task.stop.set()
            self.cancel_button.setEnabled(False)
            self.activity_label.setText('Arrêt en cours…')

    def on_error(self, message):
        self.status_label.setText('L’opération n’a pas pu être terminée.')
        self.log.appendPlainText(message)
        QMessageBox.warning(self, 'Origin Extract', message)

    def choose_project(self):
        if self.busy():
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Ouvrir un projet', str(Path.home() / 'Downloads'),
                                             'Projets Origin (*.originpack *.opju *.opj)')
        if path:
            self.open_path(Path(path))

    def choose_folder(self):
        if self.busy():
            return
        path = QFileDialog.getExistingDirectory(self, 'Ouvrir un dossier d’exports', str(Path.home() / 'Downloads'))
        if path:
            self.open_path(Path(path))

    def open_path(self, path):
        if self.busy():
            return
        path = Path(path)
        if path.is_dir():
            self.start_task(lambda task: load_export(path, task.stop, task.message.emit), 'Vérification des tableaux…', self.set_project)
        elif path.suffix.lower() in ('.originpack', '.zip'):
            self.start_task(lambda task: load_pack(path, task.stop), 'Ouverture du projet portable…', self.set_project)
        elif path.suffix.lower() in ('.opj', '.opju'):
            if sys.platform == 'win32':
                viewer = self.viewer_path()
                if not viewer:
                    self.connection()
                    viewer = self.viewer_path()
                if not viewer:
                    return
                def convert(task):
                    with tempfile.TemporaryDirectory(prefix='OriginExtract-local-') as temp:
                        return convert_windows(path, viewer, temp, task.stop, task.message.emit)
                self.start_task(convert, 'Lecture du projet Origin…', self.set_project)
            else:
                address = self.settings.value('remote/address', '')
                token = self.settings.value('remote/token', '')
                if not address or not token:
                    self.connection()
                    address = self.settings.value('remote/address', '')
                    token = self.settings.value('remote/token', '')
                if not address or not token:
                    self.status_label.setText('Ouvrez un .originpack pour le mode hors ligne, ou connectez un PC Windows.')
                    return
                self.start_task(lambda task: convert_remote(path, address, token, task.stop, task.message.emit),
                                'Connexion au PC Windows…', self.set_project)
        else:
            QMessageBox.information(self, 'Format non reconnu', 'Choisissez un .originpack, un projet .opju/.opj ou un dossier contenant _rapport.json.')

    def set_project(self, project):
        self.project = project
        self.project_title.setText(project.name)
        self.project_title.setToolTip(project.source)
        self.project_detail.setText('Projet portable · disponible hors ligne · valeurs et en-têtes conservés')
        self.update_compact()
        values = [len(project.sheets), project.row_count, sum(s.reconstructed for s in project.sheets)]
        for widget, value in zip(self.metrics, values):
            widget.setText(f'{value:,}'.replace(',', ' '))
        self.search.clear()
        self.list.blockSignals(True)
        self.list.clear()
        for index, sheet in enumerate(project.sheets):
            item = QListWidgetItem()
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setToolTip(sheet.name)
            title = sheet.name if len(sheet.name) <= 43 else sheet.name[:40] + '…'
            item.setText(f'{title}\n{len(sheet.rows):,} lignes  ·  {len(sheet.headers)} colonnes'.replace(',', ' '))
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.pages.setCurrentIndex(1)
        self.list.setCurrentRow(0)
        self.select_sheet(0)
        self.update_selection()
        self.status_label.setText(f'{len(project.sheets)} tableaux vérifiés · données prêtes à exporter')

    def select_sheet(self, index):
        if self.project is None or not 0 <= index < len(self.project.sheets):
            return
        sheet = self.project.sheets[index]
        self.sheet_title.setText(sheet.name)
        self.sheet_detail.setText(f'{len(sheet.rows):,} lignes · {len(sheet.headers)} colonnes'.replace(',', ' '))
        missing = sum(c.get('source') == 'Origin column letter' for c in sheet.record.get('column_metadata', []) or [])
        if sheet.reconstructed:
            self.provenance.setText('Noms reconstitués')
            self.provenance.setObjectName('Reconstructed')
        elif missing:
            self.provenance.setText(f'{missing} nom à préciser')
            self.provenance.setObjectName('Reconstructed')
        else:
            self.provenance.setText('Noms Origin')
            self.provenance.setObjectName('BlueBadge')
        self.provenance.style().unpolish(self.provenance)
        self.provenance.style().polish(self.provenance)
        self.provenance.setToolTip('Les noms reconstitués proviennent de la correspondance confirmée. Les autres noms sont conservés depuis Origin. Les lettres seules signalent un nom encore inconnu.')
        model = TableModel(sheet)
        self.table.setModel(model)
        self.table_model = model
        self.x_axis.blockSignals(True)
        self.y_axis.blockSignals(True)
        self.x_axis.clear()
        self.y_axis.clear()
        self.x_axis.addItems(sheet.headers)
        self.y_axis.addItems(sheet.headers)
        self.x_axis.setCurrentIndex(0)
        self.y_axis.setCurrentIndex(sheet.headers.index('X') if 'X' in sheet.headers else min(1, len(sheet.headers) - 1))
        self.x_axis.blockSignals(False)
        self.y_axis.blockSignals(False)
        self.update_plot()
        self.preview_note.setText(f'Aperçu : {min(1000, len(sheet.rows)):,} / {len(sheet.rows):,} lignes · valeurs complètes au survol. Export sans arrondi.'.replace(',', ' '))

    def update_plot(self):
        index = self.list.currentRow()
        if self.project and index >= 0 and self.x_axis.currentIndex() >= 0 and self.y_axis.currentIndex() >= 0:
            self.plot.set_data(self.project.sheets[index], self.x_axis.currentIndex(), self.y_axis.currentIndex())

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, 'Choisir le dossier de destination', self.destination.text())
        if path:
            self.destination.setText(path)
            self.settings.setValue('output', path)

    def export(self):
        if not self.project or not self.checked() or self.busy():
            return
        project, selected = self.project, self.checked()
        options = ExportOptions(self.extension.currentText().lower(), self.separator.currentData(),
                                self.headers.isChecked(), self.decimals.isChecked())
        destination = self.destination.text()
        self.start_task(lambda task: export_project(project, destination, selected, options, task.stop,
                                                    lambda c, t, s: task.progress.emit(c, t, s)),
                        'Préparation de l’export…', self.exported)

    def exported(self, folder):
        self.last_output = Path(folder)
        self.status_label.setText(f'Export terminé · {folder}')
        dialog = QMessageBox(self)
        dialog.setWindowTitle('Export terminé')
        dialog.setText('Vos tableaux sont prêts.')
        dialog.setInformativeText(str(folder))
        open_button = dialog.addButton('Ouvrir le dossier', QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton('Fermer', QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() == open_button:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def save_pack(self):
        if not self.project or self.busy():
            return
        selected = self.checked()
        if not selected:
            QMessageBox.information(self, 'Aucun tableau sélectionné', 'Sélectionnez les tableaux à partager.')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Créer un projet portable',
                                             str(Path.home() / 'Downloads' / (self.project.name + '.originpack')),
                                             'Projet portable (*.originpack)')
        if path:
            if not path.lower().endswith('.originpack'):
                path += '.originpack'
            project = replace(self.project, sheets=[self.project.sheets[i] for i in selected])
            self.start_task(lambda task: write_pack(project, path, task.stop), 'Création du projet pour Mac…',
                            lambda result: self.status_label.setText(f'Projet portable créé · {result}'))

    def connection(self):
        ConnectionDialog(self).exec()

    def toggle_log(self):
        self.log.setVisible(not self.log.isVisible())

    def help(self):
        QMessageBox.information(self, 'Guide rapide',
            '1. Ouvrez un .opju sur Windows, ou un .originpack sur Mac et Windows.\n\n'
            '2. Cochez les tableaux, vérifiez les colonnes et l’aperçu des courbes.\n\n'
            '3. Exportez vers un nouveau dossier : les en-têtes sont inclus par défaut.\n\n'
            'POUR LE MAC\nCréez un projet pour Mac depuis Windows et transférez le .originpack. '
            'Il fonctionne ensuite hors ligne, sans Origin Viewer.\n\n'
            'Pour de nouveaux .opju directement depuis le Mac : démarrez le relais Windows '
            'et renseignez son adresse et sa clé dans Connexion Mac et PC. Le PC doit rester allumé.\n\n'
            'Les noms reconstitués sont indiqués dans l’interface et dans le rapport d’export.')

    def dragEnterEvent(self, event):
        if not self.busy() and event.mimeData().hasUrls() and event.mimeData().urls()[0].isLocalFile():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self.open_path(Path(urls[0].toLocalFile()))
            event.acceptProposedAction()

    def closeEvent(self, event):
        if self.busy():
            self.cancel_task()
            self.status_label.setText('Arrêt demandé. Attendez la fin avant de fermer la fenêtre.')
            event.ignore()
            return
        if self.bridge is not None:
            with self.bridge.lock:
                running = any(j.state in ('en_attente', 'conversion') for j in self.bridge.jobs.values())
            if running:
                QMessageBox.information(self, 'Conversion du Mac en cours', 'Attendez la fin de la conversion avant de fermer ce PC.')
                event.ignore()
                return
            self.bridge.close()
        event.accept()


class SheetDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(180, 44)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(option.rect).adjusted(0, 2, -1, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setPen(Qt.PenStyle.NoPen)
        if selected:
            painter.setBrush(QColor('#30203f'))
            painter.drawRoundedRect(area, 8, 8)
        box = QRectF(area.left() + 9, area.center().y() - 6, 12, 12)
        checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked.value
        painter.setPen(QPen(QColor('#a17cc7' if checked else '#5d466f'), 1))
        painter.setBrush(QColor('#ab84dc' if checked else '#18101f'))
        painter.drawRoundedRect(box, 3, 3)
        if checked:
            painter.setPen(QPen(QColor('#21132e'), 1.7))
            path = QPainterPath()
            path.moveTo(box.left() + 3, box.top() + 6)
            path.lineTo(box.left() + 5, box.top() + 8)
            path.lineTo(box.left() + 9, box.top() + 4)
            painter.drawPath(path)
        lines = str(index.data(Qt.ItemDataRole.DisplayRole) or '').split('\n', 1)
        font = QFont('Nunito')
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor('#eadcf8' if selected else '#c4afda'))
        width = max(20, int(area.width() - 38))
        title = QFontMetrics(font).elidedText(lines[0], Qt.TextElideMode.ElideMiddle, width)
        painter.drawText(QRectF(area.left() + 30, area.top() + 4, width, 17), title)
        painter.setPen(QColor('#9c83b0' if selected else '#786486'))
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        if len(lines) > 1:
            painter.drawText(QRectF(area.left() + 30, area.top() + 22, width, 14), lines[1])
        painter.restore()

    def editorEvent(self, event, model, option, index):
        click = event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton
        space = event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Space
        if space or (click and option.rect.left() <= event.position().x() <= option.rect.left() + 27):
            checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked.value
            model.setData(index, Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
            return True
        return False


class Window(LegacyWindow):
    """Interface compacte ; le moteur et les formats restent communs aux deux plateformes."""
    def __init__(self):
        QMainWindow.__init__(self)
        apply_appearance(QApplication.instance())
        self.settings = QSettings('OriginExtract', 'OriginExtract')
        self.project = None
        self.task = None
        self.bridge = None
        self.last_output = None
        self.setWindowTitle(f'Origin Extract — {__author__}')
        self.setWindowIcon(app_icon())
        self.setMinimumSize(760, 500)
        self.resize(920, 600)
        self.setAcceptDrops(True)
        shell = QWidget()
        shell.setObjectName('Shell')
        self.setCentralWidget(shell)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(9)
        top = QHBoxLayout()
        logo = label()
        logo.setPixmap(app_icon().pixmap(30, 30))
        top.addWidget(logo)
        top.addWidget(label('origin extract', 'Brand'))
        top.addStretch()
        self.open_button = button('＋  Ouvrir', self.choose_project)
        top.addWidget(self.open_button)
        more = button('···', name='IconButton')
        menu = QMenu(more)
        menu.addAction('Ouvrir un dossier', self.choose_folder)
        self.pack_button = menu.addAction('Partager un .originpack', self.save_pack)
        self.pack_button.setEnabled(False)
        menu.addSeparator()
        menu.addAction('Mac ↔ PC', self.connection)
        menu.addAction('Journal', self.toggle_log)
        menu.addAction('Guide', self.help)
        menu.addSeparator()
        menu.addAction('À propos', self.about)
        more.setMenu(menu)
        top.addWidget(more)
        layout.addLayout(top)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.build_empty())
        self.pages.addWidget(self.build_workspace())
        layout.addWidget(self.pages, 1)
        self.activity, inner = card(QVBoxLayout, margin=8)
        inner.setSpacing(5)
        row = QHBoxLayout()
        self.activity_label = label('', 'Subtitle')
        self.activity_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.activity_label, 1)
        self.cancel_button = button('×', self.cancel_task, 'IconButton')
        row.addWidget(self.cancel_button)
        inner.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        inner.addWidget(self.progress)
        self.activity.hide()
        layout.addWidget(self.activity)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setMaximumHeight(85)
        self.log.hide()
        layout.addWidget(self.log)
        bottom = QHBoxLayout()
        author = label(__author__, 'Author')
        author.setToolTip('Auteur de l’application')
        bottom.addWidget(author)
        bottom.addStretch()
        self.status_label = label('Prêt', 'Subtitle')
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        bottom.addWidget(self.status_label, 1)
        self.last_output_button = button('Ouvrir le dossier', self.open_output, 'TextButton')
        self.last_output_button.hide()
        bottom.addWidget(self.last_output_button)
        self.mode_label = label(self.default_mode(), 'Subtitle')
        bottom.addWidget(self.mode_label)
        layout.addLayout(bottom)

    def default_mode(self):
        return 'Windows' if sys.platform == 'win32' else 'Mac'

    def build_empty(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        drop, center = card(QVBoxLayout, 'Hero', 30)
        center.addStretch()
        icon = label()
        icon.setPixmap(app_icon().pixmap(62, 62))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.addWidget(icon)
        text = label('Glisser un projet', 'Title')
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.addWidget(text)
        text = label('.opju  ·  .originpack', 'Subtitle')
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.addWidget(text)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(button('Choisir un fichier', self.choose_project, 'Primary'))
        row.addStretch()
        center.addLayout(row)
        center.addStretch()
        outer.addWidget(drop)
        return page

    def build_workspace(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        source = QHBoxLayout()
        self.project_title = label('', 'FileTitle')
        self.project_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        source.addWidget(self.project_title, 1)
        self.project_detail = label('', 'Subtitle')
        source.addWidget(self.project_detail)
        outer.addLayout(source)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(8)
        collection, left = card(QVBoxLayout, margin=10)
        left.setSpacing(7)
        heading = QHBoxLayout()
        heading.addWidget(label('Feuilles', 'SectionTitle'))
        heading.addStretch()
        self.selection_label = label('', 'Subtitle')
        heading.addWidget(self.selection_label)
        heading.addWidget(button('☑', self.toggle_selection, 'TextButton'))
        left.addLayout(heading)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Filtrer…')
        self.search.textChanged.connect(self.filter_sheets)
        left.addWidget(self.search)
        self.list = QListWidget()
        self.list.setItemDelegate(SheetDelegate(self.list))
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentRowChanged.connect(self.select_sheet)
        self.list.itemChanged.connect(self.update_selection)
        left.addWidget(self.list, 1)
        collection.setMinimumWidth(178)
        split.addWidget(collection)
        preview, right = card(QVBoxLayout, margin=10)
        right.setSpacing(6)
        heading = QHBoxLayout()
        self.sheet_title = label('', 'FileTitle')
        self.sheet_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        heading.addWidget(self.sheet_title, 1)
        self.provenance = label('', 'BlueBadge')
        heading.addWidget(self.provenance)
        right.addLayout(heading)
        self.sheet_detail = label('', 'Subtitle')
        right.addWidget(self.sheet_detail)
        tabs = QTabWidget()
        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setDefaultSectionSize(78)
        self.table.verticalHeader().setDefaultSectionSize(27)
        self.table.verticalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        tabs.addTab(self.table, 'Données')
        graph = QWidget()
        graph_layout = QVBoxLayout(graph)
        graph_layout.setContentsMargins(0, 5, 0, 0)
        axes = QHBoxLayout()
        axes.addWidget(label('X', 'Subtitle'))
        self.x_axis = QComboBox()
        axes.addWidget(self.x_axis, 1)
        axes.addWidget(label('Y', 'Subtitle'))
        self.y_axis = QComboBox()
        axes.addWidget(self.y_axis, 1)
        self.x_axis.currentIndexChanged.connect(self.update_plot)
        self.y_axis.currentIndexChanged.connect(self.update_plot)
        graph_layout.addLayout(axes)
        self.plot = Plot()
        self.plot.setMinimumHeight(145)
        graph_layout.addWidget(self.plot, 1)
        tabs.addTab(graph, 'Courbe')
        right.addWidget(tabs, 1)
        self.preview_note = label('', 'Subtitle')
        right.addWidget(self.preview_note)
        split.addWidget(preview)
        split.setSizes([205, 670])
        outer.addWidget(split, 1)
        footer = QHBoxLayout()
        self.options_button = button('TXT · TAB', self.export_settings)
        footer.addWidget(self.options_button)
        self.destination = QLineEdit(self.settings.value('output', str(Path.home() / 'Downloads/Exports_Origin')))
        self.destination.hide()
        self.destination_button = button('Destination', self.choose_output, 'TextButton')
        self.destination_button.setToolTip(self.destination.text())
        footer.addWidget(self.destination_button)
        footer.addStretch()
        self.export_button = button('Exporter', self.export, 'Primary')
        self.export_button.setMinimumWidth(135)
        footer.addWidget(self.export_button)
        outer.addLayout(footer)
        self.extension, self.separator = QComboBox(self), QComboBox(self)
        self.extension.addItems(['TXT', 'CSV'])
        for text, value in [('Tabulations', '\t'), ('Point-virgule', ';'), ('Virgule', ',')]:
            self.separator.addItem(text, value)
        self.headers = QCheckBox(self)
        self.headers.setChecked(True)
        self.decimals = QCheckBox(self)
        self.decimals.setChecked(True)
        for widget in (self.extension, self.separator, self.headers, self.decimals):
            widget.hide()
        return page

    def update_compact(self):
        pass

    def resizeEvent(self, event):
        QMainWindow.resizeEvent(self, event)
        if self.project is not None and hasattr(self, 'project_title'):
            self.elide(self.project_title, self.project.name)
            index = self.list.currentRow()
            if index >= 0:
                self.elide(self.sheet_title, self.project.sheets[index].name)

    def elide(self, widget, text):
        widget.setToolTip(text)
        widget.setText(widget.fontMetrics().elidedText(text, Qt.TextElideMode.ElideMiddle, max(60, widget.width())))

    def set_project(self, project):
        self.project = project
        self.search.blockSignals(True)
        self.search.clear()
        self.list.blockSignals(True)
        self.list.clear()
        for index, sheet in enumerate(project.sheets):
            item = QListWidgetItem()
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setText(f'{sheet.name}\n{len(sheet.rows):,} × {len(sheet.headers)}'.replace(',', ' '))
            item.setToolTip(sheet.name)
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.search.blockSignals(False)
        self.pages.setCurrentIndex(1)
        self.project_detail.setText(f'{len(project.sheets)} feuilles · {project.row_count:,} lignes'.replace(',', ' '))
        self.elide(self.project_title, project.name)
        self.list.setCurrentRow(0)
        self.select_sheet(0)
        self.update_selection()
        self.status_label.setText('Prêt')
        QTimer.singleShot(50, lambda: self.elide(self.project_title, self.project.name) if self.project else None)

    def select_sheet(self, index):
        if self.project is None or not 0 <= index < len(self.project.sheets):
            return
        sheet = self.project.sheets[index]
        self.elide(self.sheet_title, sheet.name)
        self.sheet_detail.setText(f'{len(sheet.rows):,} lignes · {len(sheet.headers)} colonnes'.replace(',', ' '))
        missing = sum(c.get('source') == 'Origin column letter' for c in sheet.record.get('column_metadata', []) or [])
        self.provenance.setObjectName('Reconstructed' if sheet.reconstructed or missing else 'BlueBadge')
        self.provenance.setText('Reconstitué' if sheet.reconstructed else f'{missing} à nommer' if missing else 'Origin')
        self.provenance.setToolTip('Noms reconstitués selon la correspondance confirmée.' if sheet.reconstructed else 'Noms conservés depuis Origin.' if not missing else 'Une lettre seule indique un nom encore inconnu.')
        self.provenance.style().unpolish(self.provenance)
        self.provenance.style().polish(self.provenance)
        self.table_model = TableModel(sheet)
        self.table.setModel(self.table_model)
        for combo in (self.x_axis, self.y_axis):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(sheet.headers)
        self.x_axis.setCurrentIndex(0)
        self.y_axis.setCurrentIndex(sheet.headers.index('X') if 'X' in sheet.headers else min(1, len(sheet.headers) - 1))
        for combo in (self.x_axis, self.y_axis):
            combo.blockSignals(False)
        self.update_plot()
        self.preview_note.setText(f'{min(1000, len(sheet.rows)):,} lignes affichées · export intégral'.replace(',', ' '))
        self.preview_note.setToolTip('Valeurs complètes au survol. Aucun arrondi dans les exports.')

    def update_selection(self):
        count = len(self.checked())
        self.selection_label.setText(f'{count}/{self.list.count()}')
        self.export_button.setText(f'Exporter ({count})')
        self.export_button.setEnabled(bool(count) and not self.busy())

    def on_log(self, message):
        self.log.appendPlainText(message)
        self.elide(self.activity_label, message)

    def on_error(self, message):
        self.status_label.setText('Échec de l’opération')
        self.log.appendPlainText(message)
        QMessageBox.warning(self, 'Origin Extract', message)

    def choose_output(self):
        super().choose_output()
        self.destination_button.setToolTip(self.destination.text())

    def export_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Export')
        dialog.setMinimumWidth(310)
        form = QVBoxLayout(dialog)
        form.setContentsMargins(18, 18, 18, 18)
        form.addWidget(label('Export', 'Title'))
        row = QHBoxLayout()
        extension, separator = QComboBox(), QComboBox()
        extension.addItems(['TXT', 'CSV'])
        extension.setCurrentIndex(self.extension.currentIndex())
        separator.addItems(['Tabulations', 'Point-virgule', 'Virgule'])
        separator.setCurrentIndex(self.separator.currentIndex())
        row.addWidget(extension)
        row.addWidget(separator, 1)
        form.addLayout(row)
        headers = QCheckBox('Noms de colonnes')
        headers.setChecked(self.headers.isChecked())
        decimals = QCheckBox('Point décimal')
        decimals.setChecked(self.decimals.isChecked())
        form.addWidget(headers)
        form.addWidget(decimals)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.extension.setCurrentIndex(extension.currentIndex())
            self.separator.setCurrentIndex(separator.currentIndex())
            self.headers.setChecked(headers.isChecked())
            self.decimals.setChecked(decimals.isChecked())
            self.options_button.setText(f'{extension.currentText()} · ' + ['TAB', ';', ','][separator.currentIndex()])
            self.options_button.setToolTip('En-têtes inclus' if headers.isChecked() else 'Sans en-têtes')

    def exported(self, folder):
        self.last_output = Path(folder)
        self.last_output_button.show()
        self.status_label.setText('Export terminé')
        self.status_label.setToolTip(str(folder))

    def open_output(self):
        if self.last_output:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output)))

    def about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('À propos')
        dialog.setFixedWidth(330)
        form = QVBoxLayout(dialog)
        form.setContentsMargins(22, 22, 22, 22)
        form.addWidget(label('origin extract', 'Brand'))
        form.addWidget(label(f'Créé par {__author__}', 'SectionTitle'))
        form.addWidget(label(f'Version {__version__} · © {__author__}', 'Subtitle'))
        form.addSpacing(12)
        form.addWidget(button('Fermer', dialog.accept))
        dialog.exec()

    def help(self):
        guide = ROOT / 'GUIDE_WINDOWS_MAC.txt'
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(guide)))

    def showEvent(self, event):
        super().showEvent(event)
        if sys.platform == 'win32':
            try:
                import ctypes
                enabled = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(int(self.winId()), 20, ctypes.byref(enabled), 4)
            except (OSError, AttributeError):
                pass


def run(open_path=None):
    app = QApplication(sys.argv[:1])
    app.setApplicationName('Origin Extract')
    app.setOrganizationName(__author__)
    app.setApplicationVersion(__version__)
    apply_appearance(app)
    window = Window()
    window.show()
    if open_path:
        QTimer.singleShot(120, lambda: window.open_path(Path(open_path)))
    return app.exec()

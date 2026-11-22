from pathlib import Path
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

PURPLE = '#b392ff'
_loaded = False


def load_fonts():
    global _loaded
    if _loaded:
        return
    for path in (Path(__file__).resolve().parents[1] / 'assets/fonts').glob('*.ttf'):
        QFontDatabase.addApplicationFont(str(path))
    _loaded = True


def apply_appearance(app):
    load_fonts()
    app.setStyle('Fusion')
    app.setFont(QFont('Nunito', 10))
    palette = QPalette()
    colors = {'Window': '#0c0a10', 'WindowText': '#f2ecfa', 'Base': '#15121b',
              'AlternateBase': '#191520', 'Text': '#eae2f4', 'Button': '#221a2d',
              'ButtonText': '#f2ecfa', 'Highlight': '#6f469f', 'HighlightedText': '#ffffff',
              'ToolTipBase': '#30243f', 'ToolTipText': '#f2ecfa', 'PlaceholderText': '#796e87'}
    for role, color in colors.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)


STYLE = '''
QWidget { font-family: "Nunito", "Segoe UI", sans-serif; font-size: 12px; color: #ece4f5; }
QMainWindow, QWidget#Shell, QDialog { background: #0c0a10; }
QLabel#Brand { font-family: "Fredoka"; font-size: 24px; font-weight: 500; color: #f1e7ff; }
QLabel#Title, QLabel#HeroTitle { font-family: "Fredoka"; font-size: 24px; font-weight: 500; color: #e9d9ff; }
QLabel#SectionTitle { font-family: "Fredoka"; font-size: 16px; font-weight: 500; color: #eee3fa; }
QLabel#FileTitle { font-family: "Nunito"; font-size: 12px; font-weight: 700; color: #d6c6e8; }
QLabel#Subtitle, QLabel#Body, QLabel#Eyebrow { color: #92849f; font-size: 11px; }
QLabel#Author { font-family: "Nunito"; color: #a18ab8; font-size: 10px; font-weight: 700; }
QLabel#Badge, QLabel#BlueBadge { color: #cbb1ef; background: #281d36; border: 1px solid #3c2a50; border-radius: 7px; padding: 2px 7px; font-size: 10px; }
QLabel#Reconstructed { color: #d9b9fa; background: #30203d; border: 1px solid #4d315f; border-radius: 7px; padding: 2px 7px; font-size: 10px; }
QFrame#Card, QWidget#Card { background: #15121b; border: 1px solid #2c2336; border-radius: 12px; }
QFrame#Hero { background: #15101d; border: 1px dashed #58416d; border-radius: 16px; }
QPushButton { background: #201928; border: 1px solid #392b46; border-radius: 8px; padding: 6px 11px; min-height: 18px; font-weight: 700; }
QPushButton:hover { background: #2b1f38; border-color: #70518c; }
QPushButton:pressed { background: #3a2750; }
QPushButton:disabled { color: #6b5e79; background: #19131f; border-color: #251c2e; }
QPushButton#Primary { font-family: "Fredoka"; background: #b795ff; color: #1d102f; border: 1px solid #b795ff; font-size: 14px; padding: 7px 17px; font-weight: 500; }
QPushButton#Primary:hover { background: #cfb5ff; border-color: #cfb5ff; }
QPushButton#Primary:pressed { background: #9b6cea; }
QPushButton#Primary:disabled { background: #4c3867; color: #9c83b5; border-color: #4c3867; }
QPushButton#TextButton { color: #bb9add; background: transparent; border: none; padding: 3px 6px; }
QPushButton#TextButton:hover { background: #2b1d38; }
QPushButton#IconButton { font-size: 17px; padding: 3px; min-width: 27px; max-width: 27px; min-height: 27px; max-height: 27px; border-radius: 8px; }
QLineEdit, QComboBox { background: #100d16; border: 1px solid #35283f; border-radius: 7px; padding: 5px 8px; min-height: 18px; selection-background-color: #654288; color: #e4d5f2; }
QLineEdit:focus, QComboBox:focus { border-color: #a67ada; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #201728; color: #eadcf6; border: 1px solid #4b3462; selection-background-color: #4b3268; }
QCheckBox { spacing: 7px; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #69517e; border-radius: 4px; background: #17101f; }
QCheckBox::indicator:checked { background: #aa80e6; border-color: #aa80e6; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { border: none; padding: 0px; }
QTabWidget::pane { background: #15121b; border: none; }
QTabBar::tab { background: transparent; color: #8c7a9d; border-bottom: 2px solid transparent; padding: 6px 10px; margin-right: 9px; font-weight: 700; }
QTabBar::tab:selected { color: #c4a0ff; border-bottom: 2px solid #c4a0ff; }
QTableView { font-family: "JetBrains Mono", "Consolas", monospace; font-size: 10px; background: #15121b; alternate-background-color: #19141f; gridline-color: #292030; border: none; selection-background-color: #3a2851; selection-color: #f5edff; }
QHeaderView::section { font-family: "Nunito"; font-size: 10px; font-weight: 800; background: #1c1525; color: #bfa4d6; padding: 6px 5px; border: none; border-bottom: 1px solid #34223f; }
QTableCornerButton::section { background: #1c1525; border: none; }
QScrollBar:vertical { background: transparent; width: 7px; margin: 1px; }
QScrollBar::handle:vertical { background: #4f3762; border-radius: 3px; min-height: 22px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { background: transparent; height: 7px; }
QScrollBar::handle:horizontal { background: #4f3762; border-radius: 3px; min-width: 22px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QProgressBar { border: none; background: #2a1b38; border-radius: 2px; min-height: 3px; max-height: 3px; }
QProgressBar::chunk { background: #b08be9; border-radius: 2px; }
QPlainTextEdit { background: #120d19; border: 1px solid #30203e; border-radius: 8px; padding: 6px; font-family: "JetBrains Mono", monospace; font-size: 10px; color: #aa92bf; }
QMenu { background: #1c1425; border: 1px solid #4a315e; border-radius: 8px; padding: 5px; }
QMenu::item { padding: 7px 18px; border-radius: 5px; }
QMenu::item:selected { background: #42295b; }
QMenu::item:disabled { color: #71617f; }
QMenu::separator { height: 1px; background: #392747; margin: 4px 6px; }
QToolTip { background: #30203f; color: #f0e4fc; border: 1px solid #65487d; padding: 5px; font-size: 11px; }
'''

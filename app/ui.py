"""Professional PySide6 desktop UI. All labels are kept separate from registry logic."""
from __future__ import annotations
import ctypes
import os
import sys
from pathlib import Path

from PySide6.QtCore import (QAbstractTableModel, QByteArray, QModelIndex, QPoint,
                            QSortFilterProxyModel, Qt, QSize, QUrl)
from PySide6.QtGui import (QAction, QColor, QDesktopServices, QFont, QIcon,
                           QPainter, QPixmap, QShortcut, QKeySequence)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFileDialog, QFileIconProvider, QFormLayout, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QSizePolicy, QStyledItemDelegate, QStyle, QTableView,
    QVBoxLayout, QWidget
)

from .icons import svg_data
from .models import MenuEntry
from .registry_backend import ContextRegistry, RegistryError, CONTEXTS, resolve_icon_location
from .settings import read_settings, write_settings
from .theme import EN, HE, PALETTE, stylesheet

CATEGORIES = ('all', 'desktop', 'folders', 'files', 'drives')


def graphic(name: str, color: str = '#83ACF9', size: int = 20) -> QIcon:
    svg = QSvgRenderer(QByteArray(svg_data(name, color, size)))
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    svg.render(painter)
    painter.end()
    return QIcon(pix)


def window_icon() -> QIcon:
    return graphic('logo', '#519CFA', 48)


def titlebar_theme(hwnd: int, dark: bool) -> None:
    """Use the supported Win10/11 DWM title-bar color preference when available."""
    if sys.platform != 'win32':
        return
    try:
        val = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd), attr, ctypes.byref(val), ctypes.sizeof(val))
            if result == 0:
                break
    except (OSError, AttributeError, ValueError):
        pass


class EntryModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.entries: list[MenuEntry] = []
        self.language = 'he'
        self._files = QFileIconProvider()
        self._icon_cache: dict[str, QIcon] = {}

    def set_entries(self, entries: list[MenuEntry]) -> None:
        self.beginResetModel()
        self.entries = entries
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else 6

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            t = HE if self.language == 'he' else EN
            return [t['item'], t['program'], t['kind'], t['where'], t['root'], t['status']][section]
        return None

    def entry(self, row: int) -> MenuEntry | None:
        return self.entries[row] if 0 <= row < len(self.entries) else None

    def icon_for(self, entry: MenuEntry) -> QIcon:
        location = resolve_icon_location(entry.icon_location, entry.command)
        if location and os.path.isfile(location):
            if location not in self._icon_cache:
                from PySide6.QtCore import QFileInfo
                icon = self._files.icon(QFileInfo(location))
                if not icon.isNull():
                    self._icon_cache[location] = icon
            if location in self._icon_cache:
                return self._icon_cache[location]
        return graphic('puzzle' if entry.kind == 'extension' else 'file', '#83ACF9', 22)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        e = self.entry(index.row())
        if e is None:
            return None
        col = index.column()
        t = HE if self.language == 'he' else EN
        if role == Qt.ItemDataRole.DisplayRole:
            return [e.name, e.source, t['extension'] if e.kind == 'extension' else t['command'],
                    t[e.category], e.root_name, t['off'] if e.is_disabled else t['on']][col]
        if role == Qt.ItemDataRole.DecorationRole and col == 0:
            return self.icon_for(e)
        if role == Qt.ItemDataRole.ToolTipRole:
            return f'{e.name}\n{e.registry_path}\n{e.command or e.clsid}'
        if role == Qt.ItemDataRole.UserRole:
            return e.id
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeading
        if role == Qt.ItemDataRole.ForegroundRole and col == 4:
            return QColor(PALETTE['dark']['muted'])
        return None


class EntryFilter(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.category = 'all'
        self.keyword = ''
        self.setDynamicSortFilter(True)

    def filterAcceptsRow(self, row: int, parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return False
        e = model.entry(row)
        if e is None:
            return False
        if self.category != 'all' and e.category != self.category:
            return False
        if self.keyword:
            hay = ' '.join((e.name, e.source, e.command, e.clsid, e.registry_path, e.category_label)).casefold()
            if self.keyword.casefold() not in hay:
                return False
        return True

    def set_category(self, category: str) -> None:
        self.category = category
        self.invalidateFilter()

    def set_keyword(self, keyword: str) -> None:
        self.keyword = keyword.strip()
        self.invalidateFilter()


class StatusDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index) -> None:
        if index.column() != 5:
            return super().paint(painter, option, index)
        e = index.model().sourceModel().entry(index.model().mapToSource(index).row())
        light = QApplication.instance().property('prsf_light_theme') is True
        color = ('#118366' if light else '#45D6AB') if not e.is_disabled else ('#98610E' if light else '#EBC47D')
        bg = ('#E4F5EC' if light else '#123B35') if not e.is_disabled else ('#FFF4DB' if light else '#3C3024')
        if option.state & QStyle.StateFlag.State_Selected:
            bg = '#254A59'
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = option.rect.adjusted(12, 11, -10, -11)
        r.setWidth(min(r.width(), 82))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(r, 10, 10)
        painter.setPen(QColor(color))
        f = painter.font()
        f.setPointSize(9)
        f.setWeight(QFont.Weight.DemiBold)
        painter.setFont(f)
        painter.drawText(r, Qt.AlignmentFlag.AlignCenter, str(index.data()))
        painter.restore()


class StatCard(QFrame):
    def __init__(self, caption: str, icon: str, tone: str):
        super().__init__()
        self.setObjectName('statCard')
        self.setMinimumHeight(105)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(17, 14, 17, 14)
        copy = QVBoxLayout()
        copy.setSpacing(7)
        self.number = QLabel('—')
        self.number.setObjectName('statNumber')
        self.text = QLabel(caption)
        self.text.setObjectName('statText')
        copy.addWidget(self.number)
        copy.addWidget(self.text)
        lay.addLayout(copy, 1)
        self.icon = QLabel()
        self.icon.setPixmap(graphic(icon, tone, 28).pixmap(28, 28))
        self.icon.setFixedSize(38, 38)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.icon)


class ProgramDialog(QDialog):
    def __init__(self, parent: QWidget, language='he'):
        super().__init__(parent)
        self.language = language
        self.setWindowTitle('הוסף תוכנה לתפריט' if language == 'he' else 'Add context menu program')
        self.setMinimumWidth(520)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(16)
        heading = QLabel('הוספת פקודה חדשה' if language == 'he' else 'Add a new command')
        heading.setObjectName('pageTitle')
        layout.addWidget(heading)
        note = QLabel('הפקודה תתווסף רק לחשבון Windows הנוכחי.' if language == 'he'
                      else 'The command will be installed for your Windows account only.')
        note.setObjectName('hint')
        layout.addWidget(note)
        form = QFormLayout()
        form.setSpacing(13)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('לדוגמה: פתח בעורך שלי' if language == 'he' else 'e.g. Open with my editor')
        form.addRow('שם בתפריט' if language == 'he' else 'Menu label', self.name_edit)
        pathrow = QHBoxLayout()
        self.exe_edit = QLineEdit()
        self.exe_edit.setPlaceholderText('C:\\Program Files\\...' )
        browse = QPushButton('עיון…' if language == 'he' else 'Browse…')
        browse.clicked.connect(self.choose_program)
        pathrow.addWidget(self.exe_edit, 1)
        pathrow.addWidget(browse)
        form.addRow('קובץ EXE' if language == 'he' else 'Executable', pathrow)
        self.arguments_edit = QLineEdit()
        self.arguments_edit.setPlaceholderText('פרמטרים נוספים (לא חובה)' if language == 'he' else 'Optional arguments')
        form.addRow('פרמטרים' if language == 'he' else 'Arguments', self.arguments_edit)
        layout.addLayout(form)
        layout.addWidget(QLabel('היכן להציג את הפקודה?' if language == 'he' else 'Show this command for:'))
        self.checks = {}
        t = HE if language == 'he' else EN
        for key in ('desktop', 'folders', 'files', 'drives'):
            chk = QCheckBox(t[key])
            chk.setChecked(key in ('desktop', 'folders'))
            self.checks[key] = chk
            layout.addWidget(chk)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('הוסף תוכנה' if language == 'he' else 'Add program')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('ביטול' if language == 'he' else 'Cancel')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose_program(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'בחר תוכנה' if self.language == 'he' else 'Choose program',
                                                  '', 'Applications (*.exe)')
        if filename:
            self.exe_edit.setText(filename)
            if not self.name_edit.text().strip():
                self.name_edit.setText(Path(filename).stem)

    def values(self) -> tuple[list[str], str, str, str]:
        selected = [name for name, box in self.checks.items() if box.isChecked()]
        return selected, self.name_edit.text(), self.exe_edit.text(), self.arguments_edit.text()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = read_settings()
        self.theme = self.settings['theme']
        self.language = self.settings['language']
        self.layout_mode = self.settings['layout']
        self.registry = ContextRegistry()
        self.entries: list[MenuEntry] = []
        self.category = 'all'
        self.model = EntryModel(self)
        self.proxy = EntryFilter(self)
        self.proxy.setSourceModel(self.model)
        self.setWindowTitle('PrsfMenuForge — Context Menu Manager')
        self.setWindowIcon(window_icon())
        self.resize(1370, 850)
        self.setMinimumSize(1050, 700)
        self._build_ui()
        self._apply_theme()
        self._apply_labels()
        self._apply_layout()
        self._shortcuts()
        if self.settings.get('geometry'):
            try:
                self.restoreGeometry(QByteArray.fromHex(self.settings['geometry'].encode('ascii')))
            except (ValueError, TypeError):
                pass
        self.refresh()

    @property
    def tr(self) -> dict[str, str]:
        return HE if self.language == 'he' else EN

    def make_button(self, text: str, symbol: str, callback, name='') -> QPushButton:
        btn = QPushButton(text)
        if name:
            btn.setObjectName(name)
        btn.setIcon(graphic(symbol))
        btn.setIconSize(QSize(18, 18))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(callback)
        return btn

    def _build_ui(self):
        root = QWidget()
        root.setObjectName('shell')
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.sidebar = QWidget()
        self.sidebar.setObjectName('sidebar')
        self.sidebar.setFixedWidth(231)
        nav = QVBoxLayout(self.sidebar)
        nav.setContentsMargins(17, 25, 17, 18)
        nav.setSpacing(8)
        brandrow = QHBoxLayout()
        self.brand_icon = QLabel()
        self.brand_icon.setPixmap(window_icon().pixmap(38, 38))
        self.brand = QLabel('PrsfMenuForge')
        self.brand.setObjectName('brand')
        brandrow.addWidget(self.brand_icon)
        brandrow.addWidget(self.brand, 1)
        nav.addLayout(brandrow)
        self.nav_caption = QLabel()
        self.nav_caption.setObjectName('navCaption')
        nav.addSpacing(35)
        nav.addWidget(self.nav_caption)
        nav.addSpacing(9)
        symbols = {'all': 'grid', 'desktop': 'monitor', 'folders': 'folder', 'files': 'file', 'drives': 'drive'}
        self.nav_buttons = {}
        for key in CATEGORIES:
            button = self.make_button('', symbols[key], lambda checked=False, k=key: self.select_category(k), 'nav')
            button.setMinimumHeight(45)
            nav.addWidget(button)
            self.nav_buttons[key] = button
        nav.addStretch(1)
        safety = QFrame()
        safety.setObjectName('panel')
        safe_layout = QVBoxLayout(safety)
        safe_layout.setContentsMargins(15, 16, 15, 16)
        header = QHBoxLayout()
        safe_icon = QLabel()
        safe_icon.setPixmap(graphic('shield', '#39D3A3', 21).pixmap(21, 21))
        header.addWidget(safe_icon)
        self.safe_title = QLabel('גיבוי ושחזור')
        self.safe_title.setObjectName('sectionTitle')
        header.addWidget(self.safe_title, 1)
        safe_layout.addLayout(header)
        self.safe_note = QLabel('גיבוי אוטומטי לפני מחיקה או שינוי של פריטים קיימים.')
        self.safe_note.setWordWrap(True)
        self.safe_note.setObjectName('hint')
        safe_layout.addWidget(self.safe_note)
        nav.addWidget(safety)
        self.sidebar_admin = self.make_button('', 'lock', self.run_admin)
        nav.addWidget(self.sidebar_admin)
        outer.addWidget(self.sidebar)

        self.body = QWidget()
        self.body.setObjectName('body')
        content = QVBoxLayout(self.body)
        content.setContentsMargins(28, 24, 28, 18)
        content.setSpacing(17)
        outer.addWidget(self.body, 1)

        header = QHBoxLayout()
        intro = QVBoxLayout()
        intro.setSpacing(4)
        self.heading = QLabel()
        self.heading.setObjectName('pageTitle')
        self.description = QLabel()
        self.description.setObjectName('hint')
        intro.addWidget(self.heading)
        intro.addWidget(self.description)
        header.addLayout(intro, 1)
        self.layout_button = self.make_button('', 'layout', self.toggle_layout, 'iconButton')
        self.language_button = self.make_button('', 'globe', self.toggle_language, 'iconButton')
        self.theme_button = self.make_button('', 'moon', self.toggle_theme, 'iconButton')
        self.backup_button = self.make_button('', 'backup', self.open_backups)
        self.refresh_button = self.make_button('', 'refresh', self.refresh)
        self.add_button = self.make_button('', 'plus', self.add_program, 'primary')
        for btn in (self.layout_button, self.language_button, self.theme_button):
            btn.setFixedSize(40, 40)
            btn.setText('')
        for btn in (self.layout_button, self.language_button, self.theme_button,
                    self.backup_button, self.refresh_button, self.add_button):
            header.addWidget(btn)
        content.addLayout(header)

        summary = QHBoxLayout()
        summary.setSpacing(13)
        self.card_total = StatCard('', 'grid', '#539AFB')
        self.card_active = StatCard('', 'check', '#39D3A3')
        self.card_hidden = StatCard('', 'eye-off', '#F7C778')
        for card in (self.card_total, self.card_active, self.card_hidden):
            summary.addWidget(card, 1)
        content.addLayout(summary)

        listing = QFrame()
        listing.setObjectName('panel')
        table_box = QVBoxLayout(listing)
        table_box.setContentsMargins(0, 0, 0, 0)
        table_box.setSpacing(0)
        tools = QHBoxLayout()
        tools.setContentsMargins(17, 15, 17, 14)
        tools.setSpacing(13)
        self.list_title = QLabel()
        self.list_title.setObjectName('sectionTitle')
        tools.addWidget(self.list_title)
        self.count = QLabel()
        self.count.setObjectName('caption')
        tools.addWidget(self.count)
        tools.addStretch(1)
        self.search = QLineEdit()
        self.search.setMinimumWidth(280)
        self.search.setMaximumWidth(420)
        self.search.addAction(graphic('search'), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self.search_changed)
        tools.addWidget(self.search)
        table_box.addLayout(tools)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setItemDelegateForColumn(5, StatusDelegate(self.table))
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(49)
        head = self.table.horizontalHeader()
        head.setStretchLastSection(True)
        head.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col, size in ((1, 165), (2, 103), (3, 130), (4, 78), (5, 100)):
            head.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(col, size)
        self.table.selectionModel().selectionChanged.connect(self.entry_changed)
        table_box.addWidget(self.table, 1)
        self.no_results = QLabel()
        self.no_results.setObjectName('hint')
        self.no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_results.setMinimumHeight(35)
        table_box.addWidget(self.no_results)
        content.addWidget(listing, 1)

        details = QFrame()
        details.setObjectName('detailsPanel')
        detail_box = QVBoxLayout(details)
        detail_box.setContentsMargins(18, 15, 18, 15)
        detail_box.setSpacing(8)
        self.details_title = QLabel()
        self.details_title.setObjectName('sectionTitle')
        detail_box.addWidget(self.details_title)
        self.detail_name = QLabel()
        self.detail_name.setObjectName('hint')
        detail_box.addWidget(self.detail_name)
        self.detail_path = QLineEdit()
        self.detail_path.setReadOnly(True)
        self.detail_path.setMinimumHeight(32)
        self.detail_path.setPlaceholderText('Registry')
        self.detail_path.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        detail_box.addWidget(self.detail_path)
        self.detail_command = QLineEdit()
        self.detail_command.setReadOnly(True)
        self.detail_command.setMinimumHeight(32)
        self.detail_command.setPlaceholderText('Command / CLSID')
        self.detail_command.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        detail_box.addWidget(self.detail_command)
        content.addWidget(details)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.status_icon = QLabel()
        self.status_icon.setPixmap(graphic('info', '#7AAAF0', 19).pixmap(19, 19))
        actions.addWidget(self.status_icon)
        self.status_label = QLabel()
        self.status_label.setObjectName('statusText')
        actions.addWidget(self.status_label, 1)
        self.hide_button = self.make_button('', 'eye-off', self.toggle_selected)
        self.remove_button = self.make_button('', 'trash', self.delete_selected, 'danger')
        self.hide_button.setMinimumWidth(140)
        self.remove_button.setMinimumWidth(120)
        self.hide_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        actions.addWidget(self.hide_button)
        actions.addWidget(self.remove_button)
        content.addLayout(actions)

    def _shortcuts(self):
        QShortcut(QKeySequence('Ctrl+F'), self, activated=self.search.setFocus)
        QShortcut(QKeySequence('F5'), self, activated=self.refresh)
        QShortcut(QKeySequence('Ctrl+N'), self, activated=self.add_program)

    def _apply_layout(self):
        direction = Qt.LayoutDirection.RightToLeft if self.layout_mode == 'rtl' else Qt.LayoutDirection.LeftToRight
        self.setLayoutDirection(direction)
        # Registry keys and executable paths are always LTR regardless of interface layout.
        for editor in (self.detail_path, self.detail_command):
            editor.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.layout_button.setToolTip(self.tr['layout'] + ': ' + self.tr[self.layout_mode])

    def _apply_theme(self):
        QApplication.instance().setProperty('prsf_light_theme', self.theme == 'light')
        self.setStyleSheet(stylesheet(self.theme))
        self.theme_button.setIcon(graphic('sun' if self.theme == 'dark' else 'moon'))
        self.theme_button.setToolTip(self.tr['light'] if self.theme == 'dark' else self.tr['dark'])
        titlebar_theme(int(self.winId()), self.theme == 'dark')
        self.update_nav_buttons()

    def _apply_labels(self):
        t = self.tr
        self.heading.setText(t['title'])
        self.description.setText(t['subtitle'])
        self.nav_caption.setText(t['menu'])
        self.card_total.text.setText(t['total'])
        self.card_active.text.setText(t['active'])
        self.card_hidden.text.setText(t['disabled'])
        self.list_title.setText(t['overview'])
        self.search.setPlaceholderText(t['search'])
        self.refresh_button.setText(t['refresh'])
        self.backup_button.setText(t['backup'])
        self.add_button.setText(t['add'])
        self.sidebar_admin.setText(t['admin'])
        self.safe_title.setText('הגנה על השינויים' if self.language == 'he' else 'Change protection')
        self.safe_note.setText('גיבוי .reg לפני שינוי או מחיקה. אפשרות שחזור ידנית.' if self.language == 'he'
                               else 'Registry backups before edits or deletion; manual restore.')
        self.details_title.setText(t['details'])
        if not self.selected_entry():
            self.detail_name.setText(t['choose'])
        self.no_results.setText(t['noresults'])
        self.status_label.setText(t['scope'])
        self.language_button.setToolTip(t['language'] + ': ' + ('עברית' if self.language == 'he' else 'English'))
        self.layout_button.setToolTip(t['layout'] + ': ' + t[self.layout_mode])
        self.theme_button.setToolTip(t['light'] if self.theme == 'dark' else t['dark'])
        self.model.language = self.language
        self.model.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, 5)
        if self.model.rowCount():
            self.model.dataChanged.emit(self.model.index(0, 0), self.model.index(self.model.rowCount()-1, 5))
        self.update_nav_buttons()
        self.entry_changed()

    def update_nav_buttons(self):
        t = self.tr
        for key, btn in self.nav_buttons.items():
            btn.setText(t[key])
            btn.setProperty('active', key == self.category)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    def toggle_theme(self):
        self.theme = 'light' if self.theme == 'dark' else 'dark'
        self._apply_theme()
        self._persist()

    def toggle_language(self):
        self.language = 'en' if self.language == 'he' else 'he'
        self._apply_labels()
        self._persist()

    def toggle_layout(self):
        self.layout_mode = 'ltr' if self.layout_mode == 'rtl' else 'rtl'
        self._apply_layout()
        self._persist()

    def _persist(self):
        self.settings.update(theme=self.theme, language=self.language, layout=self.layout_mode,
                             geometry=bytes(self.saveGeometry().toHex()).decode('ascii'))
        try:
            write_settings(self.settings)
        except OSError:
            pass

    def closeEvent(self, event):
        self._persist()
        super().closeEvent(event)

    def refresh(self):
        selected_id = self.selected_entry().id if self.selected_entry() else None
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            entries = self.registry.scan()
        except RegistryError as exc:
            self.error(str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.entries = entries
        self.model.set_entries(entries)
        self._update_numbers()
        self._update_count()
        self._restore_selection(selected_id)
        if not selected_id or not self.selected_entry():
            self.clear_details()

    def _restore_selection(self, selected_id: str | None):
        if not selected_id:
            return
        for row in range(self.proxy.rowCount()):
            src = self.proxy.mapToSource(self.proxy.index(row, 0))
            entry = self.model.entry(src.row())
            if entry and entry.id == selected_id:
                self.table.selectRow(row)
                return

    def select_category(self, category: str):
        self.category = category
        self.proxy.set_category(category)
        self.update_nav_buttons()
        self._update_count()
        self.table.clearSelection()
        self.clear_details()

    def search_changed(self, value: str):
        self.proxy.set_keyword(value)
        self._update_count()
        self.table.clearSelection()
        self.clear_details()

    def _update_count(self):
        self.count.setText(f'{self.proxy.rowCount()} / {len(self.entries)}')
        self.no_results.setVisible(self.proxy.rowCount() == 0)

    def _update_numbers(self):
        self.card_total.number.setText(str(len(self.entries)))
        self.card_active.number.setText(str(sum(not e.is_disabled for e in self.entries)))
        self.card_hidden.number.setText(str(sum(e.is_disabled for e in self.entries)))

    def selected_entry(self) -> MenuEntry | None:
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        return self.model.entry(self.proxy.mapToSource(index).row())

    def clear_details(self):
        self.detail_name.setText(self.tr['choose'])
        self.detail_path.clear()
        self.detail_command.clear()
        self.hide_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self.hide_button.setText(self.tr['hide'])
        self.remove_button.setText(self.tr['delete'])

    def entry_changed(self, *_):
        e = self.selected_entry()
        if e is None:
            self.clear_details()
            return
        self.detail_name.setText(f'{e.name}   •   {self.tr[e.category]}   •   {e.source}')
        self.detail_path.setText(e.registry_path)
        self.detail_command.setText(e.command or e.clsid or '—')
        editable = e.can_edit and not e.is_protected
        self.hide_button.setEnabled(editable and e.disabled_reason != 'LegacyDisable')
        self.remove_button.setEnabled(editable)
        self.hide_button.setText(self.tr['show'] if e.is_disabled else self.tr['hide'])
        self.remove_button.setText(self.tr['delete'])
        if e.is_protected:
            self.status_label.setText(self.tr['system'])
        else:
            self.status_label.setText(self.tr['scope'])

    def _show_result(self, message: str):
        self.status_label.setText(message)
        QMessageBox.information(self, 'PrsfMenuForge', message)

    def error(self, message: str):
        self.status_label.setText(message)
        QMessageBox.warning(self, 'PrsfMenuForge', message)

    def toggle_selected(self):
        e = self.selected_entry()
        if e is None:
            return
        if e.kind == 'extension':
            txt = (f'תוסף זה יכול להופיע בכמה מקומות. שינוי חסימתו עלול להשפיע על כל השימושים במזהה {e.clsid}. להמשיך?'
                   if self.language == 'he' else
                   f'This extension can appear in several menus. Blocking {e.clsid} may affect all of them. Continue?')
            if QMessageBox.question(self, self.tr['confirm'], txt) != QMessageBox.StandardButton.Yes:
                return
        try:
            result = self.registry.toggle(e)
        except RegistryError as exc:
            self.error(str(exc))
            return
        self.refresh()
        self._show_result(result)

    def delete_selected(self):
        e = self.selected_entry()
        if e is None or not e.can_edit:
            return
        message = (f'למחוק את רישום התפריט של ״{e.name}״?\n\n{e.registry_path}\n\n'
                   'התוכנה עצמה לא תימחק. לפני המחיקה יישמר גיבוי .reg; שחזור מחייב ייבוא ידני.'
                   if self.language == 'he' else
                   f'Delete the menu registration for “{e.name}”?\n\n{e.registry_path}\n\n'
                   'This will NOT uninstall the program. A .reg backup will be saved for manual restore.')
        dialog = QMessageBox(self)
        dialog.setWindowTitle(self.tr['confirm'])
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(message)
        cancel = dialog.addButton(self.tr['cancel'], QMessageBox.ButtonRole.RejectRole)
        confirm = dialog.addButton(self.tr['delete'], QMessageBox.ButtonRole.DestructiveRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        if dialog.clickedButton() is not confirm:
            return
        try:
            result = self.registry.remove(e)
        except RegistryError as exc:
            self.error(str(exc))
            return
        self.refresh()
        self._show_result(result)

    def add_program(self):
        dialog = ProgramDialog(self, self.language)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            result = self.registry.add_program(*dialog.values())
        except RegistryError as exc:
            self.error(str(exc))
            return
        self.refresh()
        self._show_result(result)

    def open_backups(self):
        self.registry.backup_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.registry.backup_dir)))

    def run_admin(self):
        try:
            self.registry.run_elevated()
        except RegistryError as exc:
            self.error(str(exc))
        else:
            self.close()

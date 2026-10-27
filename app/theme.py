"""Theming and translated UI labels, intentionally independent of RTL/LTR layout."""
from __future__ import annotations

HE = {
    'title': 'מנהל תפריט הלחיצה הימנית', 'subtitle': 'שליטה מסודרת בפקודות ותוספי Windows',
    'overview': 'סקירה', 'all': 'כל הפריטים', 'desktop': 'שולחן העבודה',
    'folders': 'תיקיות', 'files': 'קבצים', 'drives': 'כוננים', 'menu': 'מיקומי תפריט',
    'total': 'פריטים שזוהו', 'active': 'פריטים פעילים', 'disabled': 'פריטים מוסתרים',
    'search': 'חיפוש לפי שם, תוכנה או מפתח…', 'refresh': 'רענון', 'add': 'הוסף תוכנה',
    'backup': 'גיבויים', 'admin': 'הפעל כמנהל', 'light': 'מצב בהיר', 'dark': 'מצב כהה',
    'item': 'שם הפריט', 'program': 'תוכנה / מקור', 'kind': 'סוג', 'where': 'מיקום',
    'root': 'רישום', 'status': 'מצב', 'extension': 'תוסף', 'command': 'פקודה',
    'on': 'פעיל', 'off': 'מוסתר', 'details': 'פרטי הפריט', 'choose': 'בחר פריט מהרשימה כדי לצפות בפרטים',
    'action': 'פקודה / מזהה התוסף', 'registry': 'מפתח ברישום Windows',
    'hide': 'הסתר', 'show': 'הצג מחדש', 'delete': 'מחק', 'protected': 'פריט מוגן',
    'noresults': 'לא נמצאו פריטים בתצוגה הנוכחית', 'ready': 'מוכן. לא בוצעו שינויים במחשב.',
    'scope': 'פריטי תפריט קלאסיים; חלק מפקודות Windows 11 הדינמיות אינן כלולות.',
    'language': 'שפה', 'layout': 'פריסה', 'rtl': 'ימין לשמאל', 'ltr': 'שמאל לימין',
    'confirm': 'אישור פעולה', 'cancel': 'ביטול', 'yes': 'אישור', 'system': 'הפעולה אינה זמינה לפריט מוגן',
}
EN = {
    'title': 'Context menu manager', 'subtitle': 'Organize Windows shell commands and extensions',
    'overview': 'Overview', 'all': 'All items', 'desktop': 'Desktop', 'folders': 'Folders',
    'files': 'Files', 'drives': 'Drives', 'menu': 'Context locations',
    'total': 'Items detected', 'active': 'Active items', 'disabled': 'Hidden items',
    'search': 'Search names, applications, registry keys…', 'refresh': 'Refresh', 'add': 'Add program',
    'backup': 'Backups', 'admin': 'Run as admin', 'light': 'Light mode', 'dark': 'Dark mode',
    'item': 'Menu label', 'program': 'Program / source', 'kind': 'Type', 'where': 'Location',
    'root': 'Registry', 'status': 'Status', 'extension': 'Extension', 'command': 'Command',
    'on': 'Enabled', 'off': 'Hidden', 'details': 'Item details', 'choose': 'Select an item to see its details',
    'action': 'Command / extension ID', 'registry': 'Windows Registry path',
    'hide': 'Hide', 'show': 'Restore', 'delete': 'Delete', 'protected': 'Protected item',
    'noresults': 'No items match the current filters', 'ready': 'Ready. No changes have been made.',
    'scope': 'Classic context menu items only; some dynamic Windows 11 commands are not listed.',
    'language': 'Language', 'layout': 'Layout', 'rtl': 'Right to left', 'ltr': 'Left to right',
    'confirm': 'Confirm action', 'cancel': 'Cancel', 'yes': 'Confirm', 'system': 'This system item is protected',
}

PALETTE = {
    'dark': dict(bg='#0C111B', sidebar='#101826', panel='#141F2E', raised='#1A283B',
                 row='#131D2B', hover='#1C2B40', selection='#203956', fg='#ECF2FB',
                 muted='#91A4BE', subdued='#647995', line='#27384B', accent='#4A91FA',
                 accent_hover='#6AA4FF', green='#39D3A3', red='#FF6D7C', amber='#F7C778',
                 input='#111B2A'),
    'light': dict(bg='#F3F6FA', sidebar='#EAF0F7', panel='#FFFFFF', raised='#F2F6FC',
                  row='#FFFFFF', hover='#F0F6FE', selection='#E2EFFE', fg='#203049',
                  muted='#64748B', subdued='#8090A5', line='#D8E2EF', accent='#2677DE',
                  accent_hover='#155DC1', green='#118366', red='#C43449', amber='#98610E',
                  input='#F7F9FC'),
}


def stylesheet(theme: str) -> str:
    p = PALETTE[theme]
    # Using IDs prevents disabled-state styling from accidentally overriding action colors.
    return '''
    QWidget { color: %(fg)s; font-family: "Segoe UI", "Arial"; font-size: 13px; }
    QMainWindow, QWidget#shell, QDialog { background: %(bg)s; }
    QWidget#sidebar { background: %(sidebar)s; border-right: 1px solid %(line)s; }
    QWidget#body { background: %(bg)s; }
    QFrame#panel, QFrame#statCard, QFrame#detailsPanel { background: %(panel)s;
        border: 1px solid %(line)s; border-radius: 14px; }
    QLabel#brand { font-size: 19px; font-weight: 800; }
    QLabel#pageTitle { font-size: 27px; font-weight: 800; }
    QLabel#sectionTitle { font-size: 15px; font-weight: 700; }
    QLabel#hint, QLabel#caption, QLabel#statText, QLabel#statusText { color: %(muted)s; }
    QLabel#navCaption { color: %(subdued)s; font-size: 11px; font-weight: 700; }
    QLabel#statNumber { font-size: 26px; font-weight: 800; }
    QLabel#logoText { color: %(accent)s; font-weight: 800; }
    QLineEdit { background: %(input)s; border: 1px solid %(line)s;
        border-radius: 10px; padding: 11px 13px; selection-background-color: %(accent)s; }
    QLineEdit:focus { border: 1px solid %(accent)s; }
    QPushButton { background: %(raised)s; border: 1px solid %(line)s;
        border-radius: 10px; padding: 9px 13px; font-weight: 600; min-height: 22px; }
    QPushButton:hover { background: %(hover)s; border-color: %(muted)s; }
    QPushButton:disabled { color: %(subdued)s; background: %(panel)s; border-color: %(line)s; }
    QPushButton#primary { background: %(accent)s; color: #FFFFFF; border: 1px solid %(accent)s; }
    QPushButton#primary:hover { background: %(accent_hover)s; }
    QPushButton#primary:disabled { background: %(raised)s; border-color: %(line)s; color: %(subdued)s; }
    QPushButton#danger { background: transparent; color: %(red)s; border-color: %(red)s; }
    QPushButton#danger:hover { background: %(hover)s; }
    QPushButton#danger:disabled { background: %(panel)s; color: %(subdued)s; border-color: %(line)s; }
    QPushButton#nav { border: none; border-radius: 10px; background: transparent;
        padding: 11px 14px; text-align: left; font-weight: 600; }
    QPushButton#nav:hover { background: %(hover)s; }
    QPushButton#nav[active="true"] { background: %(selection)s; color: %(accent)s; }
    QPushButton#iconButton { min-width: 36px; padding: 7px; }
    QTableView { background: %(panel)s; alternate-background-color: %(row)s;
        border: 0px; border-radius: 8px; gridline-color: %(line)s;
        selection-background-color: %(selection)s; selection-color: %(fg)s;
        outline: none; }
    QTableView::item { padding: 9px 8px; border-bottom: 1px solid %(line)s; }
    QTableView::item:hover { background: %(hover)s; }
    QHeaderView::section { background: %(raised)s; color: %(muted)s;
        border: 0px; border-bottom: 1px solid %(line)s; padding: 12px 10px; font-weight: 700; }
    QScrollBar:vertical { background: %(panel)s; width: 11px; margin: 2px; }
    QScrollBar::handle:vertical { background: %(line)s; min-height: 30px; border-radius: 4px; }
    QScrollBar::handle:vertical:hover { background: %(muted)s; }
    QScrollBar:horizontal { background: %(panel)s; height: 11px; margin: 2px; }
    QScrollBar::handle:horizontal { background: %(line)s; min-width: 30px; border-radius: 4px; }
    QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
    QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
    QComboBox { background: %(input)s; padding: 10px; border: 1px solid %(line)s; border-radius: 9px; }
    QComboBox QAbstractItemView { background: %(panel)s; border: 1px solid %(line)s; }
    QCheckBox { spacing: 9px; }
    QCheckBox::indicator { width: 16px; height: 16px; }
    QMessageBox QLabel { min-width: 270px; }
    ''' % p

"""Windows Explorer context-menu registry reader and safely scoped editor.

No third-party modules. Machine keys require Windows elevation, never implicit.
Only *specific handler registrations* are deleted, not underlying applications.
All destructive writes are preceded by an exported .reg backup.
"""
from __future__ import annotations
import ctypes
import datetime as dt
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .models import MenuEntry
from .settings import data_directory

try:
    import winreg
except ImportError:
    winreg = None  # Tests and source inspection are supported on other OSes.

# These keys contain classic shell commands and traditional COM context handlers.
# Modern Windows 11 IExplorerCommand/sparse-package menus are not all exposed here.
CONTEXTS = {
    'desktop': ('שולחן העבודה', ('Directory\\Background', 'DesktopBackground')),
    'folders': ('תיקיות', ('Directory', 'Folder')),
    'files': ('קבצים', ('*', 'AllFilesystemObjects')),
    'drives': ('כוננים', ('Drive',)),
}
HIVES = (('HKCU', 'HKEY_CURRENT_USER', 'Software\\Classes'),
         ('HKLM', 'HKEY_LOCAL_MACHINE', 'Software\\Classes'))

# Prevent common built-in commands from being altered even when running elevated.
PROTECTED_NAMES = {
    'open', 'runas', 'runasuser', 'explore', 'find', 'search', 'properties',
    'new', 'print', 'printto', 'preview', 'setdesktopwallpaper', 'opennewwindow',
    'cmd', 'powershell', 'terminal', 'windows.terminal', 'share', 'delete',
    'copy', 'paste', 'cut', 'rename', 'openas', 'openwith', 'openwithlist',
}
PROTECTED_PREFIXES = ('windows.', 'microsoft.', 'shell', 'library', 'storageprovider')
DISABLE_VALUE = 'ProgrammaticAccessOnly'
BLOCKED_PATH = r'Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Blocked'
CLSID_RE = re.compile(r'^\{[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\}$')


class RegistryError(RuntimeError):
    """Safe actionable failure for display in the user interface."""


def resolve_program(command: str) -> str:
    """Return the executable file path used for application icons where possible."""
    if not command:
        return ''
    value = os.path.expandvars(command.strip())
    if value.startswith('"'):
        match = re.match(r'^"([^"]+)"', value)
        if match:
            return match.group(1)
    # Basic unquoted application path with spaces; supports `C:\...\app.exe -arg`.
    match = re.match(r'^(.*?\.(?:exe|com|bat|cmd|msc|dll))(?:\s|$)', value, re.I)
    if match:
        return match.group(1)
    return value.split(' ', 1)[0]


def resolve_icon_location(location: str, command: str = '') -> str:
    """Parse a shell Icon value such as `\"C:\\App\\foo.exe\",0`."""
    raw = os.path.expandvars((location or '').strip())
    if raw.startswith('@'):
        return resolve_program(command)
    raw = re.sub(r',-?\d+\s*$', '', raw).strip().strip('"')
    if raw and raw.lower().endswith(('.exe', '.dll', '.ico', '.png')):
        return raw
    return resolve_program(command)


def is_protected(name_key: str, display_name: str, kind: str) -> bool:
    key = name_key.casefold().strip()
    if key in PROTECTED_NAMES or any(key.startswith(x) for x in PROTECTED_PREFIXES):
        return True
    if kind == 'extension' and ('microsoft' in display_name.casefold() or 'windows' in display_name.casefold()):
        return True
    return False


def _hkey(root: str):
    if winreg is None:
        raise RegistryError('קריאת הרישום זמינה רק ב־Windows.')
    return {'HKCU': winreg.HKEY_CURRENT_USER, 'HKLM': winreg.HKEY_LOCAL_MACHINE}[root]


def _view_access(mask: int) -> int:
    # Explicit 64-bit view on x64 Windows: the Explorer process is usually 64-bit.
    return mask | (getattr(winreg, 'KEY_WOW64_64KEY', 0) if sys.maxsize > 2**32 else 0)


def _read_value(hive: str, path: str, value: str = '') -> str:
    try:
        with winreg.OpenKey(_hkey(hive), path, 0, _view_access(winreg.KEY_READ)) as handle:
            result, _ = winreg.QueryValueEx(handle, value)
            return str(result) if result is not None else ''
    except (OSError, ValueError):
        return ''


def _has_value(hive: str, path: str, value: str) -> bool:
    try:
        with winreg.OpenKey(_hkey(hive), path, 0, _view_access(winreg.KEY_READ)) as handle:
            winreg.QueryValueEx(handle, value)
            return True
    except (OSError, ValueError):
        return False


def _key_exists(hive: str, path: str) -> bool:
    try:
        with winreg.OpenKey(_hkey(hive), path, 0, _view_access(winreg.KEY_READ)):
            return True
    except OSError:
        return False


def _subkeys(hive: str, path: str) -> list[str]:
    try:
        with winreg.OpenKey(_hkey(hive), path, 0, _view_access(winreg.KEY_READ)) as handle:
            size, _, _ = winreg.QueryInfoKey(handle)
            return [winreg.EnumKey(handle, i) for i in range(size)]
    except OSError:
        return []


def _source_name(key_name: str, command: str, icon: str) -> str:
    binary = resolve_program(command) or resolve_icon_location(icon)
    if binary:
        stem = Path(binary.replace('\\', '/')).stem
        if stem and not stem.startswith('%'):
            return stem
    return key_name


def _indirect_string(raw: str) -> str:
    if not raw.startswith('@') or sys.platform != 'win32':
        return raw
    try:
        output = ctypes.create_unicode_buffer(2048)
        shell = ctypes.WinDLL('shlwapi')
        shell.SHLoadIndirectString.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        shell.SHLoadIndirectString.restype = ctypes.c_long
        if shell.SHLoadIndirectString(raw, output, len(output), None) == 0 and output.value:
            return output.value
    except (OSError, AttributeError, ValueError):
        pass
    return raw


def _blocked_guids() -> set[str]:
    out = set()
    for hive in ('HKCU', 'HKLM'):
        try:
            with winreg.OpenKey(_hkey(hive), BLOCKED_PATH, 0, _view_access(winreg.KEY_READ)) as handle:
                _, n_values, _ = winreg.QueryInfoKey(handle)
                for i in range(n_values):
                    name, _, _ = winreg.EnumValue(handle, i)
                    out.add(name.casefold())
        except OSError:
            continue
    return out


class ContextRegistry:
    def __init__(self, backup_dir: Path | None = None):
        self.backup_dir = backup_dir or data_directory() / 'Backups'

    def scan(self) -> list[MenuEntry]:
        if winreg is None:
            raise RegistryError('התוכנה מיועדת ל־Windows 10 או Windows 11 בלבד.')
        records: list[MenuEntry] = []
        blocked = _blocked_guids()
        for category, (caption, bases) in CONTEXTS.items():
            for hive, _, prefix in HIVES:
                for base in bases:
                    for kind, handler in (('command', 'shell'), ('extension', 'shellex\\ContextMenuHandlers')):
                        parent = prefix + '\\' + base + '\\' + handler
                        for child in _subkeys(hive, parent):
                            path = parent + '\\' + child
                            try:
                                entry = self._entry(category, caption, hive, path, child, kind, blocked)
                                records.append(entry)
                            except (OSError, ValueError, UnicodeError):
                                # A broken/removed registry item must not crash the entire list.
                                continue
        return sorted(records, key=lambda e: (e.category, e.name.casefold(), e.source))

    def _entry(self, category: str, caption: str, hive: str, path: str,
               name_key: str, kind: str, blocked: set[str]) -> MenuEntry:
        display = _read_value(hive, path, 'MUIVerb') or _read_value(hive, path) or name_key
        display = _indirect_string(display)
        if kind == 'command':
            command = _read_value(hive, path + '\\command')
            icon_raw = _read_value(hive, path, 'Icon')
            disabled = 'LegacyDisable' if _has_value(hive, path, 'LegacyDisable') else (
                DISABLE_VALUE if _has_value(hive, path, DISABLE_VALUE) else '')
            if _has_value(hive, path, 'Extended') and not disabled:
                # Extended means Shift-only, not disabled.
                disabled = ''
            source = _source_name(name_key, command, icon_raw)
            clsid = ''
        else:
            clsid = _read_value(hive, path).strip()
            command = ''
            icon_raw = ''
            disabled = 'Blocked COM' if clsid.casefold() in blocked else ''
            source = name_key
        core = is_protected(name_key, display, kind)
        return MenuEntry(category=category, category_label=caption, root_name=hive,
                         relative_key=path, name=display, source=source,
                         kind=kind, command=command, icon_location=icon_raw,
                         clsid=clsid, disabled_reason=disabled,
                         is_protected=core, can_edit=not core,
                         application=resolve_icon_location(icon_raw, command))

    @staticmethod
    def _validate_entry(entry: MenuEntry) -> None:
        if entry.is_protected or not entry.can_edit:
            raise RegistryError('הפריט מוגן ואינו ניתן לשינוי באמצעות הכלי.')
        path = entry.relative_key
        if entry.root_name not in ('HKCU', 'HKLM') or not path.startswith('Software\\Classes\\'):
            raise RegistryError('נתיב הרישום אינו בטווח שאפשר לשנות.')
        if entry.kind == 'command' and not path.lower().count('\\shell\\') == 1:
            raise RegistryError('אין אפשרות לערוך מפתח שאינו פקודת תפריט רגילה.')
        if entry.kind == 'extension':
            if not path.lower().count('\\shellex\\contextmenuhandlers\\') == 1:
                raise RegistryError('הכתובת אינה רישום תוסף מזוהה.')
            if not CLSID_RE.fullmatch(entry.clsid):
                raise RegistryError('מזהה התוסף אינו GUID תקין; לא ניתן לערוך אותו.')
        # Reject nested untrusted keys and ensure it is a single menu-item child.
        target_parts = ['\\shell\\', '\\shellex\\contextmenuhandlers\\']
        if not any(t in path.casefold() and path.casefold().split(t, 1)[1].count('\\') == 0 for t in target_parts):
            raise RegistryError('רק מפתח ישיר של פריט תפריט ניתן לשינוי.')

    def _backup(self, hive: str, relative_key: str, description: str) -> Path:
        """Export a *single* key to a .reg file; abort if the export fails."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = re.sub(r'[^A-Za-z0-9_-]+', '_', description)[:40]
        target = self.backup_dir / f'{stamp}_{filename}.reg'
        full_name = ('HKEY_CURRENT_USER' if hive == 'HKCU' else 'HKEY_LOCAL_MACHINE') + '\\' + relative_key
        try:
            proc = subprocess.run(['reg.exe', 'export', full_name, str(target), '/y'],
                                  capture_output=True, timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if proc.returncode != 0 or not target.is_file() or target.stat().st_size < 20:
                raise RegistryError('לא ניתן לגבות את המפתח. השינוי בוטל.')
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RegistryError(f'גיבוי הרישום נכשל; לא בוצע שינוי: {exc}') from exc
        return target

    def _set_value(self, hive: str, path: str, value_name: str, value: str | None) -> None:
        with winreg.OpenKey(_hkey(hive), path, 0, _view_access(winreg.KEY_SET_VALUE)) as key:
            if value is None:
                winreg.DeleteValue(key, value_name)
            else:
                winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, value)

    def _toggle_command(self, entry: MenuEntry) -> str:
        if entry.disabled_reason == 'LegacyDisable':
            raise RegistryError('הפריט הוסתר בשיטת LegacyDisable על ידי תוכנה אחרת; לא אשנה אותו אוטומטית.')
        if entry.disabled_reason not in ('', DISABLE_VALUE):
            raise RegistryError('סיבת ההסתרה אינה מוכרת ולכן לא בוצע שינוי.')
        backup = self._backup(entry.root_name, entry.relative_key, entry.source)
        try:
            self._set_value(entry.root_name, entry.relative_key, DISABLE_VALUE,
                            None if entry.disabled_reason else '')
        except OSError as exc:
            raise RegistryError(f'לא ניתן לערוך את המפתח. ייתכן שצריך להפעיל כמנהל. הגיבוי: {backup}') from exc
        return f'הפקודה עודכנה. גיבוי: {backup}'

    def _toggle_extension(self, entry: MenuEntry) -> str:
        if not CLSID_RE.fullmatch(entry.clsid):
            raise RegistryError('אין לתוסף GUID תקין.')
        currently_hkcu_blocked = _has_value('HKCU', BLOCKED_PATH, entry.clsid)
        if entry.is_disabled and not currently_hkcu_blocked:
            raise RegistryError('התוסף חסום ברמת המחשב. אין לשנות חסימה גלובלית בכלי זה.')
        # Back up the actual Blocked list if it exists, not only the COM registration.
        self._backup(entry.root_name, entry.relative_key, entry.source)
        backup_hint = ''
        if _subkeys('HKCU', BLOCKED_PATH) or _key_exists('HKCU', BLOCKED_PATH):
            backup_hint = str(self._backup('HKCU', BLOCKED_PATH, 'blocked_handlers'))
        # When the key does not exist, write a persistent JSON record of its prior absence.
        import json
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        record_path = self.backup_dir / f'{stamp}_extension_state.json'
        record_path.write_text(json.dumps({
            'path': 'HKCU\\' + BLOCKED_PATH,
            'guid': entry.clsid,
            'had_user_block_value': currently_hkcu_blocked,
            'action': 'restore this specific value using Registry Editor if required',
            'blocked_key_export': backup_hint,
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        try:
            if not entry.is_disabled:
                # A Blocked entry affects all contexts that use this COM class.
                with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, BLOCKED_PATH, 0,
                                        _view_access(winreg.KEY_SET_VALUE)) as key:
                    winreg.SetValueEx(key, entry.clsid, 0, winreg.REG_SZ, 'PrsfMenuForge')
            else:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, BLOCKED_PATH, 0,
                                    _view_access(winreg.KEY_SET_VALUE)) as key:
                    winreg.DeleteValue(key, entry.clsid)
        except OSError as exc:
            raise RegistryError(f'לא ניתן לשנות חסימת תוסף: {exc}') from exc
        return ('רישום חסימת תוסף עודכן. שינוי זה עשוי להשפיע על כמה תפריטים. '
                f'תיעוד מצב קודם: {record_path}' +
                (f' | גיבוי רישום החסימות: {backup_hint}' if backup_hint else ''))

    def toggle(self, entry: MenuEntry) -> str:
        self._validate_entry(entry)
        return self._toggle_command(entry) if entry.kind == 'command' else self._toggle_extension(entry)

    def remove(self, entry: MenuEntry) -> str:
        """Remove one menu registration after a backup, never its executable/COM server."""
        self._validate_entry(entry)
        backup = self._backup(entry.root_name, entry.relative_key, entry.source)
        try:
            self._delete_registry_tree(entry.root_name, entry.relative_key)
        except OSError as exc:
            raise RegistryError(f'המחיקה נכשלה; הקובץ לשחזור נמצא כאן: {backup}. {exc}') from exc
        return f'רישום התפריט הוסר. התוכנה לא נמחקה. קובץ שחזור: {backup}'

    def _delete_registry_tree(self, hive: str, path: str) -> None:
        # Use the view selected by the Python bitness; do not delete any parent keys.
        with winreg.OpenKey(_hkey(hive), path, 0, _view_access(winreg.KEY_READ | winreg.KEY_WRITE)) as key:
            names, _, _ = winreg.QueryInfoKey(key)
            children = [winreg.EnumKey(key, i) for i in range(names)]
        for child in children:
            self._delete_registry_tree(hive, path + '\\' + child)
        parent, child = path.rsplit('\\', 1)
        with winreg.OpenKey(_hkey(hive), parent, 0, _view_access(winreg.KEY_WRITE)) as parent_handle:
            winreg.DeleteKey(parent_handle, child)

    def add_program(self, categories: list[str], name: str, exe: str, args: str = '') -> str:
        """Register user-scoped commands using quoted `%V` or `%1` targets."""
        name, exe, args = name.strip(), exe.strip(), args.strip()
        if not name or not exe or not categories:
            raise RegistryError('יש לבחור יישום, להזין שם ולבחור לפחות קטגוריה אחת.')
        if not Path(exe).is_file():
            raise RegistryError('קובץ התוכנה לא נמצא. בחר קובץ EXE קיים.')
        if Path(exe).suffix.lower() != '.exe':
            raise RegistryError('למען הבטיחות ניתן להוסיף קובצי EXE בלבד.')
        if '\n' in name or len(name) > 70 or len(args) > 500:
            raise RegistryError('השם או הפרמטרים ארוכים מדי או מכילים תווים לא תקינים.')
        # Always generate unique, personally owned registry keys.
        import uuid
        batch_id = 'PrsfMenuForge_' + uuid.uuid4().hex[:16]
        added = []
        try:
            for category in dict.fromkeys(categories):
                if category not in CONTEXTS:
                    raise RegistryError('קטגוריה לא מוכרת.')
                base = CONTEXTS[category][1][0]
                full = 'Software\\Classes\\' + base + '\\shell\\' + batch_id
                target_arg = '%V' if category == 'desktop' else '%1'
                cmd = f'"{exe}" {args} "{target_arg}"'.replace('  ', ' ').strip()
                with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, full, 0,
                                        _view_access(winreg.KEY_WRITE)) as key:
                    winreg.SetValueEx(key, 'MUIVerb', 0, winreg.REG_SZ, name)
                    winreg.SetValueEx(key, 'Icon', 0, winreg.REG_SZ, exe)
                    winreg.SetValueEx(key, 'PrsfMenuForgeOwned', 0, winreg.REG_SZ, '1')
                added.append(full)
                with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, full + '\\command', 0,
                                        _view_access(winreg.KEY_WRITE)) as key:
                    winreg.SetValueEx(key, '', 0, winreg.REG_SZ, cmd)
        except (OSError, RegistryError) as exc:
            for key in reversed(added):
                try:
                    self._delete_registry_tree('HKCU', key)
                except OSError:
                    pass
            raise RegistryError(f'לא ניתן להוסיף את הפריט: {exc}') from exc
        return f'התוכנה נוספה בהצלחה אל {len(added)} תפריטים, עבור המשתמש הנוכחי.'

    @staticmethod
    def is_administrator() -> bool:
        if sys.platform != 'win32':
            return False
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (OSError, AttributeError):
            return False

    @staticmethod
    def restart_explorer() -> None:
        # Explicit opt-in, never restart Explorer during a simple registry write.
        if sys.platform != 'win32':
            raise RegistryError('פעולה זו זמינה רק ב־Windows.')
        subprocess.run(['taskkill', '/f', '/im', 'explorer.exe'],
                       capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.Popen(['explorer.exe'], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

    @staticmethod
    def run_elevated() -> None:
        if sys.platform != 'win32':
            raise RegistryError('הפעלה כמנהל זמינה ב־Windows בלבד.')
        script = str(Path(sys.argv[0]).resolve())
        # ShellExecuteW handles the UAC prompt; no scheduled task or security bypass.
        parameters = f'"{script}"'
        result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable,
                                                      parameters, None, 1)
        if result <= 32:
            raise RegistryError('בקשת הרשאות מנהל בוטלה או נכשלה.')

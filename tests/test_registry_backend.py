"""Pure-Python behavior and write safety regression tests; run without Windows or Qt."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.models import MenuEntry
from app.registry_backend import (ContextRegistry, RegistryError, is_protected,
                                  resolve_icon_location, resolve_program)


def demo(**override):
    kwargs = dict(category='desktop', category_label='שולחן העבודה', root_name='HKCU',
                  relative_key=r'Software\Classes\Directory\Background\shell\MyApp',
                  name='My App', source='MyApp', kind='command', command='"C:\\Tools\\app.exe" "%V"',
                  can_edit=True)
    kwargs.update(override)
    return MenuEntry(**kwargs)


class RegistryTests(unittest.TestCase):
    def test_command_extraction_quoted(self):
        self.assertEqual(resolve_program(r'"C:\Program Files\App\app.exe" "%V"'),
                         r'C:\Program Files\App\app.exe')

    def test_command_extraction_unquoted(self):
        self.assertEqual(resolve_program(r'C:\Tools\app.exe --open'), r'C:\Tools\app.exe')

    def test_icon_location_with_index(self):
        self.assertEqual(resolve_icon_location(r'"C:\Program Files\Editor\app.exe",0'),
                         r'C:\Program Files\Editor\app.exe')

    def test_system_builtin_protected(self):
        self.assertTrue(is_protected('runas', 'Run as administrator', 'command'))
        self.assertTrue(is_protected('Windows.MenuSomething', 'Windows', 'command'))
        self.assertFalse(is_protected('git_shell', 'Open Git Bash Here', 'command'))

    def test_entry_status(self):
        self.assertEqual(demo().status, 'פעיל')
        self.assertEqual(demo(disabled_reason='ProgrammaticAccessOnly').status, 'מוסתר')

    def test_reject_protected_before_backup(self):
        with tempfile.TemporaryDirectory() as td:
            service = ContextRegistry(Path(td))
            with patch.object(service, '_backup') as back:
                with self.assertRaises(RegistryError):
                    service.remove(demo(is_protected=True, can_edit=False))
                back.assert_not_called()

    def test_reject_non_shell_key(self):
        with self.assertRaises(RegistryError):
            ContextRegistry._validate_entry(demo(relative_key=r'Software\Classes\CLSID\random'))

    def test_reject_nested_key(self):
        with self.assertRaises(RegistryError):
            ContextRegistry._validate_entry(demo(relative_key=r'Software\Classes\Directory\shell\MyApp\command'))

    def test_reject_broken_com_identifier(self):
        with self.assertRaises(RegistryError):
            ContextRegistry._validate_entry(demo(
                relative_key=r'Software\Classes\Directory\shellex\ContextMenuHandlers\Example',
                kind='extension', clsid='something'))

    def test_failed_backup_never_deletes(self):
        service = ContextRegistry()
        with patch.object(service, '_backup', side_effect=RegistryError('failed')):
            with patch.object(service, '_delete_registry_tree') as delete:
                with self.assertRaises(RegistryError):
                    service.remove(demo())
                delete.assert_not_called()

    def test_successful_remove_calls_single_target(self):
        service = ContextRegistry()
        with patch.object(service, '_backup', return_value=Path('safe.reg')):
            with patch.object(service, '_delete_registry_tree') as delete:
                result = service.remove(demo())
                delete.assert_called_once_with('HKCU', demo().relative_key)
                self.assertIn('safe.reg', result)

    def test_reject_unsupported_windows_state(self):
        self.assertFalse(ContextRegistry.is_administrator() if __import__('sys').platform != 'win32' else False)


if __name__ == '__main__':
    unittest.main()

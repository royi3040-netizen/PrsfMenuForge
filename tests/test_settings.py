import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import settings


class SettingTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(settings, 'data_directory', return_value=Path(td)):
                saved = {'theme': 'light', 'language': 'en', 'layout': 'rtl', 'geometry': None}
                settings.write_settings(saved)
                self.assertEqual(settings.read_settings(), saved)

    def test_invalid_preference_values_are_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(settings, 'data_directory', return_value=Path(td)):
                (Path(td)/'settings.json').write_text(json.dumps({'theme':'invalid', 'layout': 'wrong'}))
                self.assertEqual(settings.read_settings()['theme'], 'dark')
                self.assertEqual(settings.read_settings()['layout'], 'rtl')


if __name__ == '__main__':
    unittest.main()

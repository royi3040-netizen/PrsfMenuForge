import unittest
import xml.etree.ElementTree as ET
from app.icons import PATHS, svg_data
from app.theme import EN, HE, stylesheet


class UIAssetTests(unittest.TestCase):
    def test_every_svg_is_well_formed(self):
        for icon in PATHS:
            self.assertEqual(ET.fromstring(svg_data(icon)).tag, '{http://www.w3.org/2000/svg}svg')

    def test_translation_keys(self):
        self.assertEqual(set(HE), set(EN))

    def test_qss_theme_variants(self):
        for theme in ('dark', 'light'):
            sheet = stylesheet(theme)
            self.assertIn('QMainWindow', sheet)
            self.assertIn('QTableView', sheet)
            self.assertIn('QScrollBar', sheet)


if __name__ == '__main__':
    unittest.main()

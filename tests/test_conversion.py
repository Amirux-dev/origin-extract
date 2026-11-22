import csv
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from origin_extract.number_text import decimal_text
from origin_extract.network import firewall_message


class NumberTests(unittest.TestCase):
    def test_complex_values_and_text(self):
        value = '-1,634526e-5 + 1,028273e+2i'
        self.assertEqual(decimal_text(value), '-1.634526e-5 + 1.028273e+2i')
        self.assertEqual(decimal_text(decimal_text(value), False), value)
        for value in ('Température, K', 'version1.2', '01:23:45', 'embedding:Graph2'):
            self.assertEqual(decimal_text(value), value)

    def test_firewall_does_not_claim_lan_connectivity(self):
        self.assertIn('blocking', firewall_message({'rules': [{'Profile': 6}]}))
        self.assertIn('Public', firewall_message({'profiles': [{'Category': 0}]}))
        self.assertIn('does not check', firewall_message({'profiles': [{'Category': 1}]}))


@unittest.skipUnless(sys.platform == 'win32', 'Automatisation Windows')
class ViewerTests(unittest.TestCase):
    def test_embedded_graphs_are_not_data(self):
        from export_origin import embedded_graph_sheet
        self.assertTrue(embedded_graph_sheet('embedding:Graph56\r\nembedding:Graph58\r\n'))
        self.assertFalse(embedded_graph_sheet('embedding:Graph56\t1.25\r\n'))
        self.assertFalse(embedded_graph_sheet(''))

    def test_ragged_rows_preserve_empty_cells_and_complex_values(self):
        from export_origin import convert_table, UnsupportedSheet
        text, rows, columns = convert_table('1,25\t-2,3 + 4,5i\t\r\n2,5\t\r\n', True)
        self.assertEqual((rows, columns), (2, 3))
        self.assertEqual(list(csv.reader(io.StringIO(text), delimiter='\t')),
                         [['1.25', '-2.3 + 4.5i', ''], ['2.5', '', '']])
        with self.assertRaises(UnsupportedSheet):
            convert_table('\r\n\t', True)


if __name__ == '__main__':
    unittest.main()

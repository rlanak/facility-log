import unittest

from app.services.number_parser import parse_quantity


class ParseQuantity(unittest.TestCase):
    """The browser reads the same strings with ui.parseQuantity (web/js/ui.js):
    a rule changed here has to change there."""

    def test_reads_what_players_type(self):
        cases = {
            "32000": 32000,
            "32.000": 32000,  # pt-BR thousands
            "2.000": 2000,
            "25.7k": 25700,
            "1,8k": 1800,
            "1.500k": 1500,
            "3K": 3000,
            "2m": 2_000_000,
            "1,5": 1.5,
            "1.5": 1.5,
            "1.50": 1.5,
            ".5": 0.5,
            " 12 ": 12,
            "0": 0,
        }
        for text, value in cases.items():
            with self.subTest(text=text):
                self.assertAlmostEqual(parse_quantity(text), value)

    def test_refuses_what_is_not_a_quantity(self):
        for text in ("", " ", "abc", "1.2.3", "1,2.3", "1.2,3", "-5", "+5", "1e5", "5kk", "5L", "k", "١٢٣", "1 000"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_quantity(text)


if __name__ == "__main__":
    unittest.main()

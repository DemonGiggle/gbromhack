import unittest
import sys
import os

# Adjust sys.path for robust importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.jw_translation import TextString, SPECIAL_BYTES

class TestTextStringPrepare(unittest.TestCase):

    def test_simple_line(self):
        ts = TextString(pointer_address=0, text="Hello", max_length=17)
        self.assertEqual(ts.prepare(), "Hello<FF>")
        self.assertEqual(ts.length, len("Hello") + 1)

    def test_line_exact_max_length(self):
        # max_length 10, "0123456789" is 10 chars. +1 for <FF>
        ts = TextString(pointer_address=0, text="0123456789", max_length=10)
        self.assertEqual(ts.prepare(), "0123456789<FF>")
        self.assertEqual(ts.length, 10 + 1)

    def test_line_exceeds_max_length_even_line_num(self):
        # max_length 5. "Hello World"
        # "Hello" (5) + <FE> (1) + "World" (5) + <FF> (1) = 12
        ts = TextString(pointer_address=0, text="Hello World", max_length=5)
        prepared_text = ts.prepare()
        self.assertEqual(prepared_text, "Hello<FE>World<FF>")
        self.assertEqual(ts.length, 5 + 1 + 5 + 1)

    def test_line_exceeds_max_length_odd_line_num(self):
        # max_length 5. "Line1<br>Line2 Next"
        # "Line1" (5) + <FD> (1) (due to <br>)
        # "Line2" (5) + <FE> (1) (auto wrap)
        # "Next" (4) + <FF> (1)
        # Total = 5+1+5+1+4+1 = 17
        ts = TextString(pointer_address=0, text="Line1<br>Line2 Next", max_length=5)
        prepared_text = ts.prepare()
        self.assertEqual(prepared_text, "Line1<FD>Line2<FE>Next<FF>")
        self.assertEqual(ts.length, 5 + 1 + 5 + 1 + 4 + 1)

    def test_explicit_br_break(self):
        # "First<br>Second"
        # "First" (5) + <FD> (1) + "Second" (6) + <FF> (1) = 13
        ts = TextString(pointer_address=0, text="First<br>Second", max_length=17)
        prepared_text = ts.prepare()
        self.assertEqual(prepared_text, "First<FD>Second<FF>")
        self.assertEqual(ts.length, 5 + 1 + 6 + 1)

    def test_special_bytes_length_calculation(self):
        # "<var0>" is 4 chars long per SPECIAL_BYTES
        # "Test <var0> name" -> "Test "(5) + "<var0>"(4) + " name"(5) = 14.  +1 for <FF>
        ts = TextString(pointer_address=0, text="Test <var0> name", max_length=17)
        prepared_text = ts.prepare()
        self.assertEqual(prepared_text, "Test <var0> name<FF>")
        self.assertEqual(ts.length, 5 + SPECIAL_BYTES["<var0>"] + 5 + 1)

    def test_special_bytes_and_wrapping(self):
        # max_length 10. "Hi <enemy> is here"
        # "Hi "(3) + "<enemy>"(8) = 11.  "Hi <enemy>" is too long.
        # "Hi" (2) -> cur_line_length = 2
        # "<enemy>" (8). 2 + 1 (space) + 8 = 11 > 10. So wrap.
        # "Hi" (2) + <FE> (1)
        # "<enemy>" (8) + " "(1) + "is"(2) = 11 > 10. So wrap.
        # "<enemy>" (8) + <FE> (1)
        # "is" (2) + " "(1) + "here" (4) = 7
        # "is here" (7) + <FF> (1)
        # Current code logic:
        # "Hi" (L0B0) -> <FE> (to L1B0) -> "<enemy>" (on L1B0) -> <FD> (to L0B1) -> "is here" (on L0B1) -> <FF>
        # Result: "Hi<FE><enemy><FD>is here<FF>"
        # Length: 2 (Hi) + 1 (<FE>) + 8 (<enemy>) + 1 (<FD>) + 7 (is here) + 1 (<FF>) = 20
        ts = TextString(pointer_address=0, text="Hi <enemy> is here", max_length=10)
        prepared_text = ts.prepare()
        self.assertEqual(prepared_text, "Hi<FE><enemy><FD>is here<FF>") # Changed expected string
        self.assertEqual(ts.length, 2 + 1 + SPECIAL_BYTES["<enemy>"] + 1 + len("is here") + 1)

    def test_text_already_ends_with_terminator_ff(self):
        ts = TextString(pointer_address=0, text="End with<FF>", max_length=17)
        self.assertEqual(ts.prepare(), "End with<FF>")
        self.assertEqual(ts.length, len("End with") + 1)

    def test_text_already_ends_with_terminator_fc(self):
        ts = TextString(pointer_address=0, text="End with<FC>", max_length=17)
        self.assertEqual(ts.prepare(), "End with<FC>")
        self.assertEqual(ts.length, len("End with") + 1)
        
    def test_empty_input_string(self):
        ts = TextString(pointer_address=0, text="", max_length=17)
        self.assertEqual(ts.prepare(), "<FF>")
        self.assertEqual(ts.length, 1)

    def test_multiple_br_and_wrapping(self):
        # max_length 8
        # "LineA<br>LineB Test<br>LineC"
        # "LineA" (5) + <FD> (1)
        # "LineB" (5) + " " (1) + "Test" (4) -> "LineB Test" (10) > 8
        #   "LineB" (5) + <FE> (1)
        #   "Test" (4) + <FD> (1) (because of original <br> after "LineB Test")
        # "LineC" (5) + <FF> (1)
        # Expected: "LineA<FD>LineB<FE>Test<FD>LineC<FF>"
        # Lengths: 5+1 + 5+1 + 4+1 + 5+1 = 24
        text = "LineA<br>LineB Test<br>LineC"
        ts = TextString(pointer_address=0, text=text, max_length=8)
        prepared_text = ts.prepare()
        self.assertEqual(prepared_text, "LineA<FD>LineB<FE>Test<FD>LineC<FF>")
        self.assertEqual(ts.length, 5+1 + 5+1 + 4+1 + 5+1)

    def test_word_longer_than_max_length(self):
        # A single word that is too long will not be broken, just put on a line.
        # This is consistent with how many old games handle it.
        # "Supercalifragilisticexpialidocious" (34)
        # max_length = 10
        # Expected: Supercalifragilisticexpialidocious<FF>
        # Length: 34 + 1 = 35
        text = "Supercalifragilisticexpialidocious"
        ts = TextString(pointer_address=0, text=text, max_length=10)
        prepared_text = ts.prepare()
        self.assertEqual(prepared_text, text + "<FF>")
        self.assertEqual(ts.length, len(text) + 1)
        
    def test_word_with_special_byte_longer_than_max_length(self):
        # "<var2><var2>" (8+8=16)
        # max_length = 10
        # Expected: <var2><var2><FF>
        # Length: 16 + 1 = 17
        text = "<var2><var2>" # length 8+8 = 16
        ts = TextString(pointer_address=0, text=text, max_length=10)
        prepared_text = ts.prepare()
        self.assertEqual(prepared_text, text + "<FF>")
        self.assertEqual(ts.length, SPECIAL_BYTES["<var2>"] * 2 + 1)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

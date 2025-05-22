import unittest
import os
import sys

# Adjust sys.path for robust importing
# Add repository root to sys.path (e.g., /app)
# This allows `from scripts.jw_patcher import ...`
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
# Add scripts directory to sys.path (e.g., /app/scripts)
# This allows modules within 'scripts' (like jw_patcher.py) to import their siblings 
# (e.g., `from jw_memorymap import ...`) directly by name.
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.jw_patcher import insert_enemy_name_loading_redirection_code, insert_enemies_code
# Ensure other necessary modules are found if jw_patcher uses them
import scripts.jw_memorymap

class TestJwPatcherApplyEnemies(unittest.TestCase):
    dummy_rom_path = "dummy_rom.gb"
    rom_size = 2 * 1024 * 1024  # 2MB

    def setUp(self):
        # Create a dummy ROM file filled with zeros
        with open(self.dummy_rom_path, 'wb') as f:
            f.write(b'\0' * self.rom_size)

    def tearDown(self):
        # Remove the dummy ROM file
        if os.path.exists(self.dummy_rom_path):
            os.remove(self.dummy_rom_path)

    def test_apply_enemies_writes_correct_bytes(self):
        # Open the dummy ROM in read/write binary mode
        with open(self.dummy_rom_path, 'rb+') as rom_file:
            # Apply the patches
            insert_enemy_name_loading_redirection_code(rom_file)
            insert_enemies_code(rom_file)

        # Re-open the ROM in read binary mode to verify
        with open(self.dummy_rom_path, 'rb') as rom_file:
            # --- Verifications for insert_enemy_name_loading_redirection_code ---
            rom_file.seek(0x0f95)
            self.assertEqual(rom_file.read(3), b'\xC3\x00\x41', "Byte mismatch at 0x0f95 for name redirection")
            
            rom_file.seek(0x0f95 + 3) # Next bytes after jp $4100
            self.assertEqual(rom_file.read(2), b'\x3E\x0C', "Byte mismatch at 0x0f95+3 for name redirection")

            rom_file.seek(0x0f95 + 5) # Next bytes after ld a, $0C
            self.assertEqual(rom_file.read(1), b'\xC7', "Byte mismatch at 0x0f95+5 for name redirection")

            offset_bank_1f = 0x1F * 0x4000 + 0x100
            rom_file.seek(offset_bank_1f)
            self.assertEqual(rom_file.read(3), b'\xFA\x9B\xC5', "Byte mismatch at 0x1F:0100 for name redirection")
            
            rom_file.seek(offset_bank_1f + 3)
            self.assertEqual(rom_file.read(1), b'\x3C', "Byte mismatch at 0x1F:0103 for name redirection")

            # --- Verifications for insert_enemies_code ---
            rom_file.seek(0x0c6e)
            self.assertEqual(rom_file.read(1), b'\x1E', "Byte mismatch at 0x0c6e for enemy code")

            rom_file.seek(0x0f9e)
            self.assertEqual(rom_file.read(2), b'\x3E\x1E', "Byte mismatch at 0x0f9e for enemy code")
            
            rom_file.seek(0x0f9e + 2)
            self.assertEqual(rom_file.read(1), b'\xC7', "Byte mismatch at 0x0f9e+2 for enemy code")

            rom_file.seek(0x0f9e + 3)
            self.assertEqual(rom_file.read(3), b'\xC3\x00\x45', "Byte mismatch at 0x0f9e+3 for enemy code")

            offset_bank_1e = 0x1E * 0x4000 + 0x500
            rom_file.seek(offset_bank_1e)
            self.assertEqual(rom_file.read(3), b'\x21\x00\x40', "Byte mismatch at 0x1E:0500 for enemy code")

            rom_file.seek(offset_bank_1e + 3)
            self.assertEqual(rom_file.read(3), b'\xCD\x71\x3A', "Byte mismatch at 0x1E:0503 for enemy code")
            
            rom_file.seek(offset_bank_1e + 6)
            self.assertEqual(rom_file.read(2), b'\x3E\x16', "Byte mismatch at 0x1E:0506 for enemy code")

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

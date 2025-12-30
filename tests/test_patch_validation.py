import sys
import unittest
from pathlib import Path
import tomllib

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from translation_table import TranslationTable
from jw_translation import TextString
from jw_memorymap import SIGNS_DATA_ALLOCATED_SPACE, ENNEMIES_DATA_ALLOCATED_SPACE


MAIN_TABLE_PATH = ROOT_DIR / "tbl" / "jw-py-en.tbl"
OVERWORLD_TABLE_PATH = ROOT_DIR / "tbl" / "jw-py-en-overworld.tbl"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_table(path: Path) -> TranslationTable:
    return TranslationTable(str(path))


def build_token_index(table: TranslationTable) -> dict[str, list[str]]:
    tokens = sorted(table.inverse_table.keys(), key=len, reverse=True)
    index: dict[str, list[str]] = {}
    for token in tokens:
        index.setdefault(token[0], []).append(token)
    return index


def encode_script(script: str, table: TranslationTable, token_index: dict[str, list[str]]) -> bytes:
    result = bytearray()
    i = 0
    while i < len(script):
        candidates = token_index.get(script[i], [])
        matched = None
        for token in candidates:
            if script.startswith(token, i):
                matched = token
                break
        if matched is None:
            snippet = script[i : i + 16]
            raise ValueError(f"Unknown token at index {i}: {snippet!r}")
        result.append(table.inverse_table[matched])
        i += len(matched)
    return bytes(result)


class PatchValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main_table = load_table(MAIN_TABLE_PATH)
        cls.overworld_table = load_table(OVERWORLD_TABLE_PATH)
        cls.main_index = build_token_index(cls.main_table)
        cls.overworld_index = build_token_index(cls.overworld_table)

    def test_no_todo_markers(self) -> None:
        issues: list[str] = []

        main_translation = load_yaml(ROOT_DIR / "src" / "jw_translation.yaml")
        for section in ("script", "combat", "combat_wide", "in_place"):
            for key, entry in (main_translation.get(section) or {}).items():
                text = str(entry.get("translation", ""))
                if "TODO" in text:
                    issues.append(f"jw_translation.yaml:{section}:{key}")

        windows = load_yaml(ROOT_DIR / "src" / "translation" / "jw_windows.yaml")
        for section in ("fullscreen", "overlay"):
            for key, entry in (windows.get(section) or {}).items():
                text = str(entry.get("translation", ""))
                if "TODO" in text:
                    issues.append(f"jw_windows.yaml:{section}:{key}")

        enemies = load_yaml(ROOT_DIR / "src" / "translation" / "jw_enemies.yaml")
        for key, entry in (enemies.get("enemies") or {}).items():
            text = str(entry.get("translated_name", ""))
            if "TODO" in text:
                issues.append(f"jw_enemies.yaml:{key}")

        signs = load_yaml(ROOT_DIR / "src" / "translation" / "jw_signs.yaml")
        for key, entry in (signs.get("signs") or {}).items():
            for line in range(3):
                text = str(entry.get(f"line{line}_translated_text", ""))
                if "TODO" in text:
                    issues.append(f"jw_signs.yaml:{key}:line{line}")

        npcs = load_yaml(ROOT_DIR / "src" / "translation" / "jw_npcs.yaml")
        for key, entry in (npcs.get("npcs") or {}).items():
            text = str(entry.get("name_translated", ""))
            if "TODO" in text:
                issues.append(f"jw_npcs.yaml:{key}")

        if issues:
            preview = ", ".join(issues[:20])
            self.fail(f"Found TODO markers in translations (first 20): {preview}")

    def test_in_place_text_does_not_overflow(self) -> None:
        data = load_yaml(ROOT_DIR / "src" / "jw_translation.yaml")
        issues: list[str] = []
        for key, entry in (data.get("in_place") or {}).items():
            original = str(entry.get("original", ""))
            translation = str(entry.get("translation", ""))
            try:
                original_bytes = encode_script(original, self.main_table, self.main_index)
                translation_bytes = encode_script(translation, self.main_table, self.main_index)
            except ValueError as exc:
                issues.append(f"in_place:{key} token error: {exc}")
                continue
            if len(translation_bytes) > len(original_bytes):
                issues.append(
                    f"in_place:{key} length {len(translation_bytes)} > {len(original_bytes)}"
                )
        if issues:
            preview = ", ".join(issues[:20])
            self.fail(f"In-place translations overflow originals (first 20): {preview}")

    def test_translation_tokens_are_encodable(self) -> None:
        issues: list[str] = []

        main_translation = load_yaml(ROOT_DIR / "src" / "jw_translation.yaml")
        sections = (("script", 17), ("combat", 10), ("combat_wide", 17))
        for section, max_len in sections:
            for key, entry in (main_translation.get(section) or {}).items():
                text = str(entry.get("translation", ""))
                ts = TextString(0, text, max_length=max_len)
                prepared = ts.prepare()
                table = self.overworld_table if entry.get("overworld", False) else self.main_table
                index = self.overworld_index if entry.get("overworld", False) else self.main_index
                try:
                    encode_script(prepared, table, index)
                except ValueError as exc:
                    issues.append(f"jw_translation.yaml:{section}:{key} token error: {exc}")

        for key, entry in (main_translation.get("in_place") or {}).items():
            text = str(entry.get("translation", ""))
            try:
                encode_script(text, self.main_table, self.main_index)
            except ValueError as exc:
                issues.append(f"jw_translation.yaml:in_place:{key} token error: {exc}")

        windows = load_yaml(ROOT_DIR / "src" / "translation" / "jw_windows.yaml")
        for section in ("fullscreen", "overlay"):
            for key, entry in (windows.get(section) or {}).items():
                text = str(entry.get("translation", ""))
                table = self.overworld_table if entry.get("overworld", False) else self.main_table
                index = self.overworld_index if entry.get("overworld", False) else self.main_index
                try:
                    encode_script(text, table, index)
                except ValueError as exc:
                    issues.append(f"jw_windows.yaml:{section}:{key} token error: {exc}")

        enemies = load_yaml(ROOT_DIR / "src" / "translation" / "jw_enemies.yaml")
        for key, entry in (enemies.get("enemies") or {}).items():
            text = str(entry.get("translated_name", ""))
            try:
                encode_script(text, self.main_table, self.main_index)
            except ValueError as exc:
                issues.append(f"jw_enemies.yaml:{key} token error: {exc}")

        signs = load_yaml(ROOT_DIR / "src" / "translation" / "jw_signs.yaml")
        for key, entry in (signs.get("signs") or {}).items():
            for line in range(3):
                text = str(entry.get(f"line{line}_translated_text", ""))
                try:
                    encode_script(text, self.main_table, self.main_index)
                except ValueError as exc:
                    issues.append(f"jw_signs.yaml:{key}:line{line} token error: {exc}")

        npcs = load_yaml(ROOT_DIR / "src" / "translation" / "jw_npcs.yaml")
        for key, entry in (npcs.get("npcs") or {}).items():
            text = str(entry.get("name_translated", ""))
            try:
                encode_script(text, self.main_table, self.main_index)
            except ValueError as exc:
                issues.append(f"jw_npcs.yaml:{key} token error: {exc}")

        if issues:
            preview = ", ".join(issues[:20])
            self.fail(f"Translation tokens not encodable (first 20): {preview}")

    def test_windows_fit_allocated_bank(self) -> None:
        windows = load_yaml(ROOT_DIR / "src" / "translation" / "jw_windows.yaml")
        total_size = 0
        issues: list[str] = []

        for section in ("fullscreen", "overlay"):
            for key, entry in (windows.get(section) or {}).items():
                win_id = int(key)
                if section == "overlay" and win_id < 0x80:
                    issues.append(f"jw_windows.yaml:overlay:{key} id < 0x80")
                text = str(entry.get("translation", ""))
                table = self.overworld_table if entry.get("overworld", False) else self.main_table
                index = self.overworld_index if entry.get("overworld", False) else self.main_index
                translation = encode_script(text, table, index)
                total_size += 6 + len(translation)

        if total_size > 0x3000:
            issues.append(f"jw_windows.yaml total data size {hex(total_size)} exceeds 0x3000")

        if issues:
            preview = ", ".join(issues[:10])
            self.fail(f"Window layout issues (first 10): {preview}")

    def test_signs_fit_allocated_ranges(self) -> None:
        signs = load_yaml(ROOT_DIR / "src" / "translation" / "jw_signs.yaml")
        total_size = 0
        current_range = 0
        base_start, base_end = SIGNS_DATA_ALLOCATED_SPACE[current_range]
        issues: list[str] = []

        for key, entry in (signs.get("signs") or {}).items():
            line_lengths = []
            for line in range(3):
                text = str(entry.get(f"line{line}_translated_text", ""))
                try:
                    encoded = encode_script(text, self.main_table, self.main_index)
                except ValueError as exc:
                    issues.append(f"jw_signs.yaml:{key}:line{line} token error: {exc}")
                    encoded = b""
                if len(encoded) > 0xFF:
                    issues.append(f"jw_signs.yaml:{key}:line{line} length {len(encoded)} > 0xFF")
                line_lengths.append(len(encoded))

            data_size = 3 + sum(line_lengths)
            if total_size + data_size > (base_end - base_start):
                current_range += 1
                if current_range >= len(SIGNS_DATA_ALLOCATED_SPACE):
                    issues.append("jw_signs.yaml exceeds allocated ranges")
                    break
                base_start, base_end = SIGNS_DATA_ALLOCATED_SPACE[current_range]
                total_size = 0

            total_size += data_size

        if issues:
            preview = ", ".join(issues[:10])
            self.fail(f"Sign data issues (first 10): {preview}")

    def test_enemies_fit_allocated_ranges(self) -> None:
        enemies = load_yaml(ROOT_DIR / "src" / "translation" / "jw_enemies.yaml")
        total_size = 0
        current_range = 0
        base_start, base_end = ENNEMIES_DATA_ALLOCATED_SPACE[current_range]
        issues: list[str] = []

        for key, entry in (enemies.get("enemies") or {}).items():
            text = str(entry.get("translated_name", ""))
            try:
                encoded = encode_script(text, self.main_table, self.main_index)
            except ValueError as exc:
                issues.append(f"jw_enemies.yaml:{key} token error: {exc}")
                encoded = b""
            data_size = 22 + len(encoded)
            if total_size + data_size > (base_end - base_start):
                current_range += 1
                if current_range >= len(ENNEMIES_DATA_ALLOCATED_SPACE):
                    issues.append("jw_enemies.yaml exceeds allocated ranges")
                    break
                base_start, base_end = ENNEMIES_DATA_ALLOCATED_SPACE[current_range]
                total_size = 0

            total_size += data_size

        if issues:
            preview = ", ".join(issues[:10])
            self.fail(f"Enemy data issues (first 10): {preview}")

    def test_script_data_fits_rom(self) -> None:
        config_path = ROOT_DIR / "config.toml"
        with config_path.open("rb") as handle:
            config = tomllib.load(handle)
        rom_path = ROOT_DIR / config["original_rom"]
        if not rom_path.exists():
            self.skipTest(f"ROM not found at {rom_path}")

        rom_size = rom_path.stat().st_size
        main_translation = load_yaml(ROOT_DIR / "src" / "jw_translation.yaml")

        messages: list[TextString] = [TextString(0, "A morning in the Jungle.<FC>")]
        sections = (("script", 17), ("combat", 10), ("combat_wide", 17))
        for section, max_len in sections:
            for entry in (main_translation.get(section) or {}).values():
                if str(entry.get("translation", "")).startswith("TODO"):
                    continue
                if entry.get("pointer_location", 0) == 0:
                    continue
                ts = TextString(entry["pointer_location"], entry["translation"], max_length=max_len)
                ts.overworld = bool(entry.get("overworld", False))
                messages.append(ts)

        data_bank = 0x11
        total_length = 0
        max_end = 0

        for msg in messages:
            prepared = msg.prepare()
            table = self.overworld_table if msg.overworld else self.main_table
            index = self.overworld_index if msg.overworld else self.main_index
            msg_bytes = encode_script(prepared, table, index)

            msg.new_bank = data_bank
            msg.new_pointer = total_length
            total_length += msg.length

            if total_length > 0x4000:
                data_bank += 1
                msg.new_bank = data_bank
                msg.new_pointer = 0
                total_length = msg.length

            end_offset = msg.new_bank * 0x4000 + msg.new_pointer + len(msg_bytes)
            max_end = max(max_end, end_offset)

        pointer_table_start = 0x10 * 0x4000 + 0x1000
        pointer_table_end = pointer_table_start + len(messages) * 3
        if pointer_table_end > (0x11 * 0x4000):
            self.fail("Pointer table exceeds bank 0x10 size")

        if max_end > rom_size:
            self.fail(f"Script data exceeds ROM size: {hex(max_end)} > {hex(rom_size)}")


if __name__ == "__main__":
    unittest.main()

"""
Unit test dasar: memastikan schema JSON valid dan (jika ada data)
setiap entri di data/ lolos validasi. Dijalankan otomatis oleh CI.
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, SchemaError

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "strongs.schema.json"


def test_schema_file_exists():
    assert SCHEMA_PATH.exists(), "schema/strongs.schema.json tidak ditemukan"


def test_schema_is_valid_json_schema():
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        schema = json.load(f)
    try:
        Draft7Validator.check_schema(schema)
    except SchemaError as e:
        pytest.fail(f"Schema tidak valid: {e}")


@pytest.mark.parametrize(
    "data_file",
    sorted(f for f in (ROOT / "data").rglob("*.json") if f.name != "stats.json") or [None],
)
def test_dataset_entries_match_schema(data_file):
    if data_file is None:
        pytest.skip("Belum ada file dataset di data/ untuk divalidasi")

    with SCHEMA_PATH.open(encoding="utf-8") as f:
        schema = json.load(f)
    validator = Draft7Validator(schema)

    with data_file.open(encoding="utf-8") as f:
        entries = json.load(f)

    assert isinstance(entries, list), f"{data_file} harus berupa list"

    all_errors = []
    for entry in entries:
        all_errors.extend(validator.iter_errors(entry))

    assert not all_errors, (
        f"{len(all_errors)} error validasi di {data_file}: "
        f"{[e.message for e in all_errors[:5]]}"
    )


def test_no_duplicate_strong_numbers():
    for data_file in sorted((ROOT / "data").rglob("*.json")):
        if data_file.name == "stats.json":
            continue
        with data_file.open(encoding="utf-8") as f:
            entries = json.load(f)
        numbers = [e.get("strong_number") for e in entries if e.get("strong_number")]
        duplicates = {n for n in numbers if numbers.count(n) > 1}
        assert not duplicates, f"Nomor Strong duplikat di {data_file}: {duplicates}"

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

from openpyxl import load_workbook


ALLOWED_INPUT_CELLS = {
    "D5",
    "D11",
    "E11",
    "D12",
    "E12",
    "D13",
    "E13",
    "D14",
    "E14",
    "D15",
    "E15",
    "D16",
    "E16",
    "D17",
    "E17",
}

FORMULA_PROTECTED_CELLS = {
    "E5",
    "H9",
    "H10",
    "H11",
    "H12",
    "H13",
    "H14",
    "H15",
    "D21",
    "E21",
    "D25",
    "E25",
    "D29",
    "E29",
}


def write_flash_report_cells(
    template_path: Path,
    output_path: Path,
    sheet_name: str,
    values: Dict[str, int],
) -> None:
    """Write report input cells only, preserving formula-protected cells."""
    disallowed = sorted(set(values) - ALLOWED_INPUT_CELLS)
    if disallowed:
        raise ValueError(f"Attempted to write non-input cells: {', '.join(disallowed)}")

    protected_overwrites = sorted(set(values) & FORMULA_PROTECTED_CELLS)
    if protected_overwrites:
        raise ValueError(f"Attempted to overwrite formula cells: {', '.join(protected_overwrites)}")

    workbook = load_workbook(template_path, data_only=False)
    if sheet_name not in workbook.sheetnames:
        raise ValueError(f"Sheet not found: {sheet_name}")
    sheet = workbook[sheet_name]

    for cell, value in values.items():
        sheet[cell] = int(value)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)


def get_formula_cells(path: Path, sheet_name: str, cells: Iterable[str]) -> Dict[str, str]:
    """Read formula values from the selected cells."""
    workbook = load_workbook(path, data_only=False)
    sheet = workbook[sheet_name]
    out: Dict[str, str] = {}
    for cell in cells:
        value = sheet[cell].value
        out[cell] = value if isinstance(value, str) else ""
    return out

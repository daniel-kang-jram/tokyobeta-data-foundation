from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook
import pytest

from scripts.flash_report_fill.excel_writer import get_formula_cells, write_flash_report_cells


def _create_template(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Flash Report（2月）"
    ws["D5"] = 100
    ws["E5"] = "=+D5/16109"
    ws["D11"] = 10
    ws["E11"] = 20
    wb.save(path)


def test_write_flash_report_cells_preserves_formula_cells(tmp_path: Path) -> None:
    template_path = tmp_path / "template.xlsx"
    output_path = tmp_path / "out.xlsx"
    _create_template(template_path)

    write_flash_report_cells(
        template_path=template_path,
        output_path=output_path,
        sheet_name="Flash Report（2月）",
        values={"D5": 123, "D11": 99},
    )

    wb = load_workbook(output_path)
    ws = wb["Flash Report（2月）"]
    assert ws["D5"].value == 123
    assert ws["D11"].value == 99
    assert ws["E5"].value == "=+D5/16109"


def test_write_flash_report_cells_blocks_formula_cell_overwrite(tmp_path: Path) -> None:
    template_path = tmp_path / "template.xlsx"
    output_path = tmp_path / "out.xlsx"
    _create_template(template_path)

    with pytest.raises(ValueError):
        write_flash_report_cells(
            template_path=template_path,
            output_path=output_path,
            sheet_name="Flash Report（2月）",
            values={"E5": 999},
        )


def test_write_flash_report_cells_blocks_non_input_cells(tmp_path: Path) -> None:
    template_path = tmp_path / "template.xlsx"
    output_path = tmp_path / "out.xlsx"
    _create_template(template_path)

    with pytest.raises(ValueError):
        write_flash_report_cells(
            template_path=template_path,
            output_path=output_path,
            sheet_name="Flash Report（2月）",
            values={"A1": 123},
        )


def test_get_formula_cells_reads_formula_values(tmp_path: Path) -> None:
    template_path = tmp_path / "template.xlsx"
    _create_template(template_path)

    formulas = get_formula_cells(
        path=template_path,
        sheet_name="Flash Report（2月）",
        cells=("E5", "D5"),
    )
    assert formulas["E5"] == "=+D5/16109"
    assert formulas["D5"] == ""

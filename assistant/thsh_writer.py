"""Fill THSH (bảng tổng hợp thiết kế xử lý nền) Excel template with segment data."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Optional

import openpyxl
from openpyxl.utils import get_column_letter

SHEET_NAME = 'THSH'

# Column mapping (1-indexed, matching the THSH sheet described in Data.xlsx)
THSH_COLS: dict[str, int] = {
    'tt':            1,
    'station_from':  2,
    'station_to':    2,   # same column – written as "from – to" text
    'length':        3,
    'mc_tinh_toan':  4,
    'borehole_ref':  5,
    'ground_elev':   6,
    'htk':           7,
    'b_nen':         8,
    # Soil layer thicknesses (cols 9-16)
    'layer_1a':      9,
    'layer_D':       10,
    'layer_1c':      11,
    'layer_2':       12,
    'layer_2a':      13,
    'layer_2b':      14,
    'layer_3':       15,
    'layer_3a':      16,
    'total_depth':   17,
    # Drainage condition col 18
    'drainage':      18,
    # Treatment cols 19-22
    'treatment_phuong_an': 19,
    'treatment':     20,
    'pvd_spacing':   21,
    'pvd_depth':     22,
    # Settlement cols 23+
    'Sc':            23,
    'Si':            24,
    'St':            25,
    'Sr':            26,
    # Stability
    'Fs':            27,
}

_LAYER_CODES = ['1a', 'D', '1c', '2', '2a', '2b', '3', '3a']


def _find_data_start_row(ws, header_text: str = 'Lý trình', max_row: int = 40) -> int:
    """Find the first data row after the header row containing header_text."""
    for row in ws.iter_rows(min_row=1, max_row=max_row):
        for cell in row:
            if cell.value and header_text in str(cell.value):
                return cell.row + 1
    # fallback: skip merged header area
    return 12


def _resolve_cell(ws, row: int, col: int):
    """Return the actual (non-merged) cell to write into for (row, col).

    openpyxl raises if you write to the top-left of a merged range without
    unmerging first.  We just return the cell object; caller decides whether
    to write.
    """
    cell = ws.cell(row=row, column=col)
    return cell


def _write_cell(ws, row: int, col: int, value: Any):
    """Write value to cell, skipping merged-cell conflicts gracefully."""
    try:
        ws.cell(row=row, column=col, value=value)
    except Exception:
        pass


def _layer_thickness(layers: list[dict], code: str) -> Optional[float]:
    """Sum thicknesses of layers matching code (case-insensitive)."""
    total = sum(
        float(lyr.get('thickness', 0.0))
        for lyr in layers
        if str(lyr.get('code', '')).strip().lower() == code.lower()
    )
    return round(total, 2) if total else None


def fill_thsh(template_path: str, output_path: str, segments: list[dict],
              start_row: Optional[int] = None) -> dict:
    """Write segment data into THSH sheet of the Excel template.

    Parameters
    ----------
    template_path : path to the .xlsx template
    output_path   : path for the output file (created from template)
    segments      : list of segment dicts (from road_segment.segments_to_dicts)
    start_row     : first data row (auto-detected if None)

    Returns
    -------
    dict with keys: output_path, rows_written, warnings
    """
    template_path = Path(template_path)
    output_path = Path(output_path)
    if not template_path.exists():
        raise FileNotFoundError(f'Template not found: {template_path}')

    shutil.copy2(template_path, output_path)

    wb = openpyxl.load_workbook(output_path)

    # Find THSH sheet
    ws = None
    for name in wb.sheetnames:
        if name.strip().upper() == SHEET_NAME:
            ws = wb[name]
            break
    if ws is None:
        wb.close()
        raise ValueError(f'Sheet "{SHEET_NAME}" not found in {template_path.name}. '
                         f'Available: {wb.sheetnames}')

    # Auto-detect start row
    if start_row is None:
        start_row = _find_data_start_row(ws)

    warnings: list[str] = []
    rows_written = 0

    for i, seg in enumerate(segments):
        row = start_row + i

        # --- Basic identity ---
        _write_cell(ws, row, THSH_COLS['tt'], seg.get('id', i + 1))

        # Station: write "from – to" in col 2 and length in col 3
        sta_from = seg.get('station_from', 0.0)
        sta_to = seg.get('station_to', 0.0)
        _write_cell(ws, row, THSH_COLS['station_from'],
                    f"Km{int(sta_from // 1000)}+{sta_from % 1000:06.1f}–"
                    f"Km{int(sta_to // 1000)}+{sta_to % 1000:06.1f}")
        _write_cell(ws, row, THSH_COLS['length'], seg.get('length'))

        # --- Profile data ---
        _write_cell(ws, row, THSH_COLS['mc_tinh_toan'],
                    f"Km{int(sta_from // 1000)}+{(sta_from + sta_to) / 2 % 1000:06.1f}")
        _write_cell(ws, row, THSH_COLS['borehole_ref'], seg.get('borehole_ref', ''))
        _write_cell(ws, row, THSH_COLS['ground_elev'], seg.get('ground_elev'))
        _write_cell(ws, row, THSH_COLS['htk'], seg.get('htk'))
        _write_cell(ws, row, THSH_COLS['b_nen'], seg.get('b_nen'))

        # --- Soil layer thicknesses ---
        layers = seg.get('layers', [])
        total_depth = 0.0
        for code in _LAYER_CODES:
            col_key = f'layer_{code.replace("-", "")}'
            t = _layer_thickness(layers, code)
            if t is not None:
                _write_cell(ws, row, THSH_COLS[col_key], t)
                total_depth += t
        _write_cell(ws, row, THSH_COLS['total_depth'],
                    round(total_depth, 2) if total_depth else seg.get('hdy'))

        # --- Treatment ---
        treatment = seg.get('treatment', '')
        _write_cell(ws, row, THSH_COLS['treatment'], treatment)
        pvd_spacing = seg.get('pvd_spacing', 0.0) or 0.0
        pvd_depth = seg.get('pvd_depth', 0.0) or 0.0
        if pvd_spacing:
            _write_cell(ws, row, THSH_COLS['pvd_spacing'], pvd_spacing)
        if pvd_depth:
            _write_cell(ws, row, THSH_COLS['pvd_depth'], pvd_depth)

        # --- Settlement & Stability ---
        for key in ('Sc', 'Si', 'St', 'Sr', 'Fs'):
            v = seg.get(key)
            if v is not None:
                col = THSH_COLS.get(key)
                if col:
                    _write_cell(ws, row, col, v)

        rows_written += 1

    wb.save(output_path)
    wb.close()

    return {
        'output_path': str(output_path),
        'rows_written': rows_written,
        'warnings': warnings,
    }

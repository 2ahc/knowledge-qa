from pathlib import Path

from openpyxl import load_workbook

from app.services.parsers.base import ParseError, Segment

MAX_ROWS_PER_SHEET = 3000


def parse(path: str | Path) -> list[Segment]:
    try:
        wb = load_workbook(str(path), read_only=True, data_only=True)
    except Exception as e:
        raise ParseError(f"Excel 文件无法解析: {e}")

    segments: list[Segment] = []
    for sheet in wb.worksheets:
        lines: list[str] = []
        truncated = False
        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i >= MAX_ROWS_PER_SHEET:
                truncated = True
                break
            cells = ["" if v is None else str(v).replace("\n", " ").strip() for v in row]
            line = " | ".join(cells).strip(" |")
            if line:
                lines.append(line)
        if not lines:
            continue
        text = "\n".join(lines)
        if truncated:
            text += f"\n（表格过长，仅保留前 {MAX_ROWS_PER_SHEET} 行）"
        segments.append(Segment(text=text, meta={"sheet": sheet.title}))
    wb.close()

    if not segments:
        raise ParseError("Excel 中没有可提取的内容")
    return segments

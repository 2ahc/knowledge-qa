from pathlib import Path

from docx import Document as DocxDocument

from app.services.parsers.base import ParseError, Segment


def parse(path: str | Path) -> list[Segment]:
    try:
        doc = DocxDocument(str(path))
    except Exception as e:
        raise ParseError(f"Word 文件无法解析: {e}")

    segments: list[Segment] = []
    current_heading = ""
    buffer: list[str] = []

    def flush():
        text = "\n".join(buffer).strip()
        if text:
            meta = {"heading": current_heading} if current_heading else {}
            segments.append(Segment(text=text, meta=meta))
        buffer.clear()

    for para in doc.paragraphs:
        style = (para.style.name or "").lower() if para.style else ""
        text = para.text.strip()
        if not text:
            continue
        if style.startswith("heading"):
            flush()
            current_heading = text
            buffer.append(text)
        else:
            buffer.append(text)
            if sum(len(s) for s in buffer) > 2000:
                flush()
    flush()

    # tables: row by row, pipe-separated
    for table in doc.tables:
        rows = []
        for row in table.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            rows.append(" | ".join(cells))
        text = "\n".join(r for r in rows if r.strip(" |"))
        if text.strip():
            segments.append(Segment(text=text, meta={"type": "table"}))

    if not segments:
        raise ParseError("Word 文档中没有可提取的文本")
    return segments

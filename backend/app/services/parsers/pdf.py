from pathlib import Path

from pypdf import PdfReader

from app.services.parsers.base import ParseError, Segment


def parse(path: str | Path) -> list[Segment]:
    try:
        reader = PdfReader(str(path))
    except Exception as e:
        raise ParseError(f"PDF 文件损坏或无法打开: {e}")

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise ParseError("PDF 已加密，请先解除加密再上传")

    segments: list[Segment] = []
    total_chars = 0
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = text.strip()
        total_chars += len(text)
        if text:
            segments.append(Segment(text=text, meta={"page": i + 1}))

    if total_chars == 0:
        raise ParseError("未检测到文本层（可能是扫描版 PDF），MVP 暂不支持 OCR")
    return segments

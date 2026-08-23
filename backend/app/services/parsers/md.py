import re
from pathlib import Path

from charset_normalizer import from_bytes

from app.services.parsers.base import ParseError, Segment


def read_text_file(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    if not raw.strip():
        raise ParseError("文件内容为空")
    # strip BOM if present
    for bom, enc in ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be")):
        if raw.startswith(bom):
            return raw.decode(enc)
    # 1) try strict UTF-8 first (most common)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    # 2) statistical detection
    guess = from_bytes(raw).best()
    if guess is not None:
        text = str(guess)
        if _looks_reasonable(text):
            return text
    # 3) common Chinese legacy encodings
    for enc in ("gb18030", "big5"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    raise ParseError("无法识别文件编码")


def _looks_reasonable(text: str) -> bool:
    """Reject decodings full of control/private-use characters."""
    if not text:
        return False
    bad = sum(1 for ch in text[:2000] if ord(ch) < 32 and ch not in "\n\r\t")
    return bad / max(len(text[:2000]), 1) < 0.05


def parse(path: str | Path) -> list[Segment]:
    """Markdown: split into sections at headings for better citation metadata."""
    text = read_text_file(path)
    segments: list[Segment] = []
    heading_re = re.compile(r"^(#{1,4})\s+(.+)$")

    current_heading = ""
    buffer: list[str] = []

    def flush():
        body = "\n".join(buffer).strip()
        if body:
            meta = {"heading": current_heading} if current_heading else {}
            segments.append(Segment(text=body, meta=meta))
        buffer.clear()

    for line in text.splitlines():
        m = heading_re.match(line.strip())
        if m:
            flush()
            current_heading = m.group(2).strip()
            buffer.append(line.strip())
        else:
            buffer.append(line)
    flush()

    if not segments:
        raise ParseError("Markdown 文件中没有内容")
    return segments


def parse_txt(path: str | Path) -> list[Segment]:
    text = read_text_file(path).strip()
    return [Segment(text=text)]

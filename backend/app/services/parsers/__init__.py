from pathlib import Path

from app.services.parsers.base import ParseError, Segment
from app.services.parsers import docx, md, pdf, xlsx

_REGISTRY = {
    "pdf": pdf.parse,
    "docx": docx.parse,
    "xlsx": xlsx.parse,
    "md": md.parse,
    "txt": md.parse_txt,
}


def parse_document(filetype: str, path: str | Path) -> list[Segment]:
    parser = _REGISTRY.get(filetype)
    if parser is None:
        raise ParseError(f"不支持的文件类型: {filetype}")
    return parser(path)

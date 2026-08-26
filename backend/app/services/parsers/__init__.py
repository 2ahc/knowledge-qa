# 解析器注册表：按文件扩展名分发到对应的解析器。
# 新增文档格式 = 写一个解析器 + 在这里注册一行。
from pathlib import Path

from app.services.parsers.base import ParseError, Segment
from app.services.parsers import docx, md, pdf, xlsx

_REGISTRY = {
    "pdf": pdf.parse,
    "docx": docx.parse,
    "xlsx": xlsx.parse,
    "md": md.parse,  # markdown 与纯文本共用解析器
    "txt": md.parse_txt,
}


def parse_document(filetype: str, path: str | Path) -> list[Segment]:
    """按文件类型选择解析器并解析。不支持的类型抛用户可读的错误。"""
    parser = _REGISTRY.get(filetype)
    if parser is None:
        raise ParseError(f"不支持的文件类型: {filetype}")
    return parser(path)

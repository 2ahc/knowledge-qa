# Markdown / 纯文本解析。
# 重点在编码探测：企业里的老文本文件经常是 GBK/GB18030 编码，直接按 UTF-8 读会乱码。
import re
from pathlib import Path

from charset_normalizer import from_bytes

from app.services.parsers.base import ParseError, Segment


def read_text_file(path: str | Path) -> str:
    """按多级策略探测编码并读取文本文件：
    1) BOM 头识别（UTF-8/UTF-16）
    2) 严格 UTF-8 解码（绝大多数现代文件）
    3) 统计探测（charset_normalizer），结果需通过"合理性"检查
    4) 兜底尝试中文常见遗留编码：GB18030（覆盖 GBK/GB2312）、Big5
    """
    raw = Path(path).read_bytes()
    if not raw.strip():
        raise ParseError("文件内容为空")
    # 按 BOM 头直接判定编码
    for bom, enc in ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be")):
        if raw.startswith(bom):
            return raw.decode(enc)
    # 1) 优先严格 UTF-8
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    # 2) 统计探测（对短文本可能误判，所以加合理性检查）
    guess = from_bytes(raw).best()
    if guess is not None:
        text = str(guess)
        if _looks_reasonable(text):
            return text
    # 3) 中文遗留编码兜底
    for enc in ("gb18030", "big5"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    raise ParseError("无法识别文件编码")


def _looks_reasonable(text: str) -> bool:
    """判断解码结果是否像正常文本：控制字符占比过高说明解错了编码。"""
    if not text:
        return False
    bad = sum(1 for ch in text[:2000] if ord(ch) < 32 and ch not in "\n\r\t")
    return bad / max(len(text[:2000]), 1) < 0.05


def parse(path: str | Path) -> list[Segment]:
    """Markdown 解析：按标题（# ~ ####）分节，标题作为出处元信息，
    让引用溯源能展示「章节名」而不是笼统的整篇文档。"""
    text = read_text_file(path)
    segments: list[Segment] = []
    heading_re = re.compile(r"^(#{1,4})\s+(.+)$")

    current_heading = ""
    buffer: list[str] = []

    def flush():
        """输出当前章节为一个文本段。"""
        body = "\n".join(buffer).strip()
        if body:
            meta = {"heading": current_heading} if current_heading else {}
            segments.append(Segment(text=body, meta=meta))
        buffer.clear()

    for line in text.splitlines():
        m = heading_re.match(line.strip())
        if m:
            # 遇到标题：结束上一节，开始新的一节
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
    """纯文本：整体作为一个文本段（无结构可分节）。"""
    text = read_text_file(path).strip()
    return [Segment(text=text)]

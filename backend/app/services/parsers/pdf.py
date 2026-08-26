# PDF 解析：逐页提取文本，页码作为出处元信息。
# 限制：不支持扫描版（图片型）PDF —— 没有文本层就需要 OCR，超出 MVP 范围，
# 此时给出明确的失败原因，避免用户不明所以。
from pathlib import Path

from pypdf import PdfReader

from app.services.parsers.base import ParseError, Segment


def parse(path: str | Path) -> list[Segment]:
    try:
        reader = PdfReader(str(path))
    except Exception as e:
        raise ParseError(f"PDF 文件损坏或无法打开: {e}")

    # 加密 PDF：先尝试空密码（部分"加密"只是权限标记，空密码可解）
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
            text = ""  # 单页提取失败不影响其他页
        text = text.strip()
        total_chars += len(text)
        if text:
            # 每页一个文本段，记录页码供引用溯源展示"第 N 页"
            segments.append(Segment(text=text, meta={"page": i + 1}))

    # 全文 0 字符 = 没有文本层，基本可断定是扫描件
    if total_chars == 0:
        raise ParseError("未检测到文本层（可能是扫描版 PDF），MVP 暂不支持 OCR")
    return segments

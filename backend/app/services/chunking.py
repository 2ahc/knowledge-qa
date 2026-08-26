"""递归文本切片：按段落/标题/句子层级切分，并合并过小的片段。

切片是检索质量的关键：
- 太大 → 向量表达不聚焦，检索不准；
- 太小 → 语义不完整，回答缺上下文。
默认 500 字一片、相邻重叠 80 字，兼顾两者。
"""
from dataclasses import dataclass, field

from app.config import settings
from app.services.parsers.base import Segment

# 分隔符优先级：先按段落切，切不动再按行、按中文句号……最后兜底按字符硬切。
# 顺序即优先级，越靠前越"语义友好"。
SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "！", "?", ";", " ", ""]


@dataclass
class ChunkSpec:
    """一个切片：正文 + 元信息（继承自解析段落的出处信息）。"""

    content: str
    meta: dict = field(default_factory=dict)


def _split_by(text: str, sep: str) -> list[str]:
    """按指定分隔符切分；空分隔符表示按单字符硬切。"""
    if sep == "":
        return list(text)
    return text.split(sep)


def _split_text(text: str, max_size: int, separators: list[str]) -> list[str]:
    """递归切分：用当前分隔符切，超长的片段换下一级分隔符继续切，
    直到所有片段都不超过 max_size（或分隔符用尽后硬切）。"""
    if len(text) <= max_size:
        return [text]

    sep = separators[0]
    rest = separators[1:]
    pieces: list[str] = []
    for part in _split_by(text, sep):
        if not part:
            continue
        if len(part) <= max_size:
            pieces.append(part)
        else:
            if not rest:
                # 分隔符用尽仍超长：按长度硬切
                for i in range(0, len(part), max_size):
                    pieces.append(part[i : i + max_size])
            else:
                pieces.extend(_split_text(part, max_size, rest))
    return pieces


def _merge_pieces(pieces: list[str], max_size: int) -> list[str]:
    """贪心合并：把相邻的小片段拼到接近 max_size，避免产生过多碎片切片。"""
    merged: list[str] = []
    buf = ""
    for p in pieces:
        candidate = f"{buf}{p}" if buf else p
        if len(candidate) <= max_size:
            buf = candidate
        else:
            if buf:
                merged.append(buf)
            buf = p
    if buf:
        merged.append(buf)
    return merged


def chunk_segments(
    segments: list[Segment],
    chunk_size: int | None = None,
    overlap: int | None = None,
    max_chunks: int | None = None,
) -> list[ChunkSpec]:
    """把解析出的段落列表切成最终切片列表。

    关键设计——重叠（overlap）：每个切片头部会带上一个切片的末尾若干字，
    这样跨切片边界的语义（比如一句话被切开）仍能在相邻切片中检索到。
    """
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap if overlap is not None else settings.chunk_overlap
    max_chunks = max_chunks or settings.max_chunks_per_doc

    chunks: list[ChunkSpec] = []
    for seg in segments:
        # 单个段落内部：先递归切分，再合并碎片
        pieces = _split_text(seg.text.strip(), chunk_size, SEPARATORS)
        pieces = _merge_pieces([p for p in pieces if p.strip()], chunk_size)
        prev_tail = ""
        for idx, piece in enumerate(pieces):
            content = piece
            if prev_tail and overlap > 0:
                # 把上一片的"尾巴"拼到本片开头，实现重叠
                content = prev_tail + content
                if len(content) > chunk_size + overlap:
                    content = content[: chunk_size + overlap]
            chunks.append(
                ChunkSpec(content=content.strip(), meta={**seg.meta, "chunk_index": idx})
            )
            # 记住本片末尾，供下一片做重叠
            prev_tail = piece[-overlap:] if overlap > 0 else ""
            # 防止超大文档无限切片
            if len(chunks) >= max_chunks:
                return chunks
    return chunks

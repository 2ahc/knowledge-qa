"""Recursive text chunking, paragraph/heading aware."""
from dataclasses import dataclass, field

from app.config import settings
from app.services.parsers.base import Segment

SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "！", "?", ";", " ", ""]


@dataclass
class ChunkSpec:
    content: str
    meta: dict = field(default_factory=dict)


def _split_by(text: str, sep: str) -> list[str]:
    if sep == "":
        return list(text)
    return text.split(sep)


def _split_text(text: str, max_size: int, separators: list[str]) -> list[str]:
    """Recursively split text into pieces <= max_size chars."""
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
                # hard cut
                for i in range(0, len(part), max_size):
                    pieces.append(part[i : i + max_size])
            else:
                pieces.extend(_split_text(part, max_size, rest))
    return pieces


def _merge_pieces(pieces: list[str], max_size: int) -> list[str]:
    """Greedily merge small pieces up to max_size."""
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
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap if overlap is not None else settings.chunk_overlap
    max_chunks = max_chunks or settings.max_chunks_per_doc

    chunks: list[ChunkSpec] = []
    for seg in segments:
        pieces = _split_text(seg.text.strip(), chunk_size, SEPARATORS)
        pieces = _merge_pieces([p for p in pieces if p.strip()], chunk_size)
        prev_tail = ""
        for idx, piece in enumerate(pieces):
            content = piece
            if prev_tail and overlap > 0:
                content = prev_tail + content
                if len(content) > chunk_size + overlap:
                    content = content[: chunk_size + overlap]
            chunks.append(
                ChunkSpec(content=content.strip(), meta={**seg.meta, "chunk_index": idx})
            )
            prev_tail = piece[-overlap:] if overlap > 0 else ""
            if len(chunks) >= max_chunks:
                return chunks
    return chunks

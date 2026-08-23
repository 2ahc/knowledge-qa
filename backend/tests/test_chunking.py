from app.services.chunking import chunk_segments
from app.services.parsers.base import Segment


def test_short_segment_single_chunk():
    chunks = chunk_segments([Segment(text="你好，世界")], chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].content == "你好，世界"


def test_long_text_split_with_overlap():
    text = "这是一个测试句子。" * 200  # ~1800 chars
    chunks = chunk_segments([Segment(text=text, meta={"page": 3})], chunk_size=200, overlap=20)
    assert len(chunks) > 1
    assert all(len(c.content) <= 220 for c in chunks)  # chunk_size + overlap cap
    # meta inherited
    assert chunks[0].meta["page"] == 3
    # overlap present: next chunk starts with tail of previous
    assert chunks[1].content[:10] in chunks[0].content


def test_paragraph_boundaries_respected():
    text = "\n\n".join(f"段落{i}。" * 30 for i in range(10))
    chunks = chunk_segments([Segment(text=text)], chunk_size=150, overlap=0)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.content) <= 150


def test_max_chunks_cap():
    segs = [Segment(text=f"文档{i}。" * 10) for i in range(100)]
    chunks = chunk_segments(segs, chunk_size=20, overlap=0, max_chunks=5)
    assert len(chunks) == 5


def test_empty_segments_ignored():
    chunks = chunk_segments([Segment(text=""), Segment(text="   ")], chunk_size=100, overlap=0)
    assert chunks == []

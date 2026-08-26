"""文档解析服务的公共定义。

每个解析器把一种格式的文件转成 Segment 列表（正文 + 出处元信息）。
出处元信息（页码/章节/工作表）会一路带到切片上，最终用于引用溯源。
解析失败请抛 ParseError —— 它的消息会直接展示给用户。
"""
from dataclasses import dataclass, field


class ParseError(Exception):
    """文档无法解析时抛出；消息是用户可读的中文原因。"""


@dataclass
class Segment:
    """一个文本段：解析器输出的最小单位，后续由切片器进一步切分。

    meta 常见键：page（PDF 页码）、heading（标题章节）、sheet（Excel 工作表）。
    """

    text: str
    meta: dict = field(default_factory=dict)

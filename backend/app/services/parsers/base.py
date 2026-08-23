"""Document parsing services.

Each parser turns a file into a list of Segments (text + location metadata).
Raise ParseError for user-readable failures (e.g. scanned PDF without text).
"""
from dataclasses import dataclass, field


class ParseError(Exception):
    """Raised when a document cannot be parsed; message is shown to users."""


@dataclass
class Segment:
    text: str
    meta: dict = field(default_factory=dict)

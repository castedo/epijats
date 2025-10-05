from __future__ import annotations

from dataclasses import dataclass

from ..tree import ArrayContent, MixedContent, ParentInline, ParentItem


@dataclass
class Paragraph(ParentItem[MixedContent]):
    def __init__(self, content: str | MixedContent = ""):
        super().__init__('p', MixedContent(content))


@dataclass
class BlockQuote(ParentItem[ArrayContent]):
    def __init__(self) -> None:
        super().__init__('blockquote', ArrayContent())


@dataclass
class IssueElement(ParentInline[str]):
    def __init__(self, msg: str):
        super().__init__('format-issue', msg)

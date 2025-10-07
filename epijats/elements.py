from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .tree import (
    ArrayContent,
    MarkupElement,
    MixedContent,
    ParentInline,
    ParentItem,
    PureElement,
)


@dataclass
class ExternalHyperlink(MarkupElement):
    def __init__(self, href: str):
        super().__init__('a')
        self.href = href
        self.xml.attrib = {'rel': 'external', 'href': href}


@dataclass
class CrossReference(MarkupElement):
    def __init__(self, rid: str):
        super().__init__('a')
        self.rid = rid
        self.xml.attrib = {"href": "#" + rid}


class Paragraph(ParentItem[MixedContent]):
    def __init__(self, content: MixedContent | str = ""):
        super().__init__('p', MixedContent(content))


class BlockQuote(ParentItem[ArrayContent]):
    def __init__(self) -> None:
        super().__init__('blockquote', ArrayContent())


class PreElement(ParentItem[MixedContent]):
    def __init__(self, content: MixedContent | str = "") -> None:
        super().__init__('pre', MixedContent(content))


class ItemElement(ParentItem[ArrayContent]):
    def __init__(self, xml_tag: str, content: Iterable[PureElement] = ()):
        super().__init__(xml_tag, ArrayContent(content))


class IssueElement(ParentInline[str]):
    def __init__(self, msg: str):
        super().__init__('format-issue', msg)

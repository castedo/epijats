from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from .tree import (
    ArrayContent,
    BiformElement,
    HtmlVoidElement,
    HtmlVoidInline,
    InlineBase,
    MarkupElement,
    MixedContent,
    ParentItem,
    PureElement,
    StartTag,
)


class LineBreak(HtmlVoidInline):
    def __init__(self) -> None:
        super().__init__('br')


class TableColumn(HtmlVoidElement):
    def __init__(self) -> None:
        super().__init__('col')


class HorizontalRule(HtmlVoidElement):
    def __init__(self) -> None:
        super().__init__('hr')


class WordBreak(HtmlVoidInline):
    def __init__(self) -> None:
        super().__init__('wbr')


@dataclass
class ExternalHyperlink(MarkupElement):
    def __init__(self, href: str):
        super().__init__('a')
        self.href = href
        self.xml.attrib = {'rel': 'external', 'href': href}


class ListItem(BiformElement):
    def __init__(self, content: Iterable[PureElement] = ()):
        super().__init__('li', ArrayContent(content))


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


@dataclass
class Citation(MarkupElement):
    def __init__(self, rid: str, rord: int):
        super().__init__(StartTag('xref', {'rid': rid, 'ref-type': 'bibr'}))
        self.rid = rid
        self.rord = rord
        self.content.append_text(str(rord))

    def matching_text(self, text: str | None) -> bool:
        return text is not None and text.strip() == self.content.text


@dataclass
class CitationTuple(InlineBase):
    _citations: list[Citation]

    def __init__(self, citations: Iterable[Citation] = ()) -> None:
        super().__init__('sup')
        self._citations = list(citations)

    @property
    def content(self) -> ArrayContent:
        return ArrayContent(self._citations)

    def __iter__(self) -> Iterator[Citation]:
        return iter(self._citations)

    def append(self, c: Citation) -> None:
        self._citations.append(c)

    def extend(self, cs: Iterable[Citation]) -> None:
        self._citations.extend(cs)

    def __len__(self) -> int:
        return len(self._citations)


class ItemElement(ParentItem[ArrayContent]):
    def __init__(self, xml_tag: str, content: Iterable[PureElement] = ()):
        super().__init__(xml_tag, ArrayContent(content))


class IssueElement(InlineBase):
    def __init__(self, msg: str):
        super().__init__('format-issue')
        self.msg = msg

    @property
    def content(self) -> str:
        return self.msg

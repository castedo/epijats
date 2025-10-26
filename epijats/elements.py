from __future__ import annotations

from collections.abc import Iterable, Iterator, MutableSequence
from dataclasses import dataclass
from typing import Generic, TypeVar
from warnings import warn

from . import tree
from .tree import (
    ArrayContent,
    HtmlVoidElement,
    HtmlVoidInline,
    InlineBase,
    MarkupElement,
    MixedContent,
    Parent,
    Element,
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


@dataclass
class CrossReference(MarkupElement):
    def __init__(self, rid: str):
        super().__init__('a')
        self.rid = rid
        self.xml.attrib = {"href": "#" + rid}


class Paragraph(Parent[MixedContent]):
    def __init__(self, content: MixedContent | str = ""):
        super().__init__('p', MixedContent(content))


class BlockQuote(Parent[ArrayContent]):
    def __init__(self) -> None:
        super().__init__('blockquote', ArrayContent())


class PreElement(Parent[MixedContent]):
    def __init__(self, content: MixedContent | str = "") -> None:
        super().__init__('pre', MixedContent(content))


ElementT = TypeVar('ElementT', bound=Element)


@dataclass
class ItemListElement(tree.ElementBase, Generic[ElementT]):
    _items: list[ElementT]

    def __init__(self, xml_tag: str, items: Iterable[ElementT] = ()):
        super().__init__(xml_tag)
        self._items = list(items)

    @property
    def content(self) -> ArrayContent:
        return ArrayContent(self._items)

    def __iter__(self) -> Iterator[ElementT]:
        return iter(self._items)

    def append(self, item: ElementT) -> None:
        self._items.append(item)

    def extend(self, items: Iterable[ElementT]) -> None:
        self._items.extend(items)

    def __len__(self) -> int:
        return len(self._items)


@dataclass
class Citation(MarkupElement):
    def __init__(self, rid: str, rord: int):
        super().__init__(StartTag('xref', {'rid': rid, 'ref-type': 'bibr'}))
        self.rid = rid
        self.rord = rord
        self.content.append_text(str(rord))

    def matching_text(self, text: str | None) -> bool:
        return text is not None and text.strip() == self.content.text


class CitationTuple(ItemListElement[Citation], tree.Inline):
    tail: str = ""

    def __init__(self, citations: Iterable[Citation] = ()) -> None:
        super().__init__('sup', citations)


class ItemElement(Parent[ArrayContent]):
    def __init__(self, xml_tag: str, content: Iterable[Element] = ()):
        super().__init__(xml_tag, ArrayContent(content))
        warn("Use specific element class for specific tag", DeprecationWarning)


class ListItem(tree.BiformElement):
    def __init__(self, content: Iterable[Element] = ()):
        super().__init__('li', ArrayContent(content))


class OrderedList(ItemListElement[ListItem]):
    def __init__(self, items: Iterable[ListItem] = ()):
        super().__init__('ol', items)


class UnorderedList(ItemListElement[ListItem]):
    def __init__(self, items: Iterable[ListItem] = ()):
        super().__init__('ul', items)


class DTerm(tree.BiformElement):
    def __init__(self, content: Iterable[Element] = ()):
        super().__init__('dt', content)


class DDefinition(tree.BiformElement):
    def __init__(self, content: Iterable[Element] = ()):
        super().__init__('dd', content)


class DItem(tree.ElementBase):
    def __init__(self, term: DTerm, definitions: Iterable[DDefinition] = ()):
        super().__init__('div')
        self.term = term
        self.definitions: MutableSequence[DDefinition] = list(definitions)

    @property
    def content(self) -> ArrayContent:
        return ArrayContent([self.term, *self.definitions])


@dataclass
class DList(ItemListElement[DItem]):
    def __init__(self, items: Iterable[DItem] = ()):
        super().__init__('dl', items)


class IssueElement(InlineBase):
    def __init__(self, msg: str):
        super().__init__('format-issue')
        self.msg = msg

    @property
    def content(self) -> str:
        return self.msg

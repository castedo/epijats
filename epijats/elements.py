from __future__ import annotations

from collections.abc import Iterable, Iterator, MutableSequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from .tree import (
    ArrayContent,
    BiformElement,
    Element,
    HtmlVoidElement,
    MixedContent,
    MixedParent,
    StartTag,
)


class LineBreak(HtmlVoidElement):
    def __init__(self) -> None:
        super().__init__('br')


class TableColumn(HtmlVoidElement):
    def __init__(self) -> None:
        super().__init__('col')


class HorizontalRule(HtmlVoidElement):
    def __init__(self) -> None:
        super().__init__('hr')


class WordBreak(HtmlVoidElement):
    def __init__(self) -> None:
        super().__init__('wbr')


@dataclass
class ExternalHyperlink(MixedParent):
    def __init__(self, href: str):
        super().__init__('a')
        self.href = href
        self.xml.attrib = {'rel': 'external', 'href': href}


@dataclass
class CrossReference(MixedParent):
    def __init__(self, rid: str):
        super().__init__('a')
        self.rid = rid
        self.xml.attrib = {"href": "#" + rid}


class Paragraph(MixedParent):
    def __init__(self, content: MixedContent | str = ""):
        super().__init__('p', content)


class BlockQuote(BiformElement):
    def __init__(self) -> None:
        super().__init__('blockquote', ArrayContent())


class Preformat(MixedParent):
    def __init__(self, content: MixedContent | str = "") -> None:
        super().__init__('pre', content)


ElementT = TypeVar('ElementT', bound=Element)


@dataclass
class ItemListElement(Element, Generic[ElementT]):
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
class Citation(MixedParent):
    def __init__(self, rid: str, rord: int):
        super().__init__(StartTag('xref', {'rid': rid, 'ref-type': 'bibr'}))
        self.rid = rid
        self.rord = rord
        self.append(str(rord))

    def matching_text(self, text: str | None) -> bool:
        return text is not None and text.strip() == self.content.text


class CitationTuple(ItemListElement[Citation], Element):
    def __init__(self, citations: Iterable[Citation] = ()) -> None:
        super().__init__('sup', citations)


class ListItem(BiformElement):
    def __init__(self, content: Iterable[Element] = ()):
        super().__init__('li', ArrayContent(content))


class List(ItemListElement[ListItem]):
    def __init__(self, items: Iterable[ListItem] = (), *, ordered: bool):
        super().__init__('ol' if ordered else 'ul', items)


class DTerm(MixedParent):
    def __init__(self, content: MixedContent | str = ""):
        super().__init__('dt', content)


class DDefinition(BiformElement):
    def __init__(self, content: Iterable[Element] = ()):
        super().__init__('dd', content)


class DItem(Element):
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


class IssueElement(Element):
    def __init__(self, msg: str):
        super().__init__('format-issue')
        self.msg = msg

    @property
    def content(self) -> str:
        return self.msg

from __future__ import annotations

from collections.abc import Iterable, Iterator, MutableSequence
from dataclasses import dataclass
from typing import TypeVar
from warnings import warn

from .condition import FormatIssue

from .tree import (
    ArrayContent,
    BiformElement,
    Element,
    FormatIssueElement,
    HtmlVoidElement,
    MixedContent,
    MixedParent,
    MutableArrayContent,
    Parent,
    StartTag,
)


class LineBreak(HtmlVoidElement):
    TAG = 'br'


class HorizontalRule(HtmlVoidElement):
    TAG = 'hr'


class WordBreak(HtmlVoidElement):
    TAG = 'wbr'


@dataclass
class ExternalHyperlink(MixedParent):
    TAG = StartTag('a', {'rel': 'external'})

    def __init__(self, href: str):
        super().__init__(None)
        self.href = href

    @property
    def xml(self) -> StartTag:
        extra = {'href': self.href} if self.href else {}
        return StartTag(self.tag, extra)


@dataclass
class CrossReference(MixedParent):
    TAG = 'a'

    def __init__(self, rid: str):
        super().__init__(None)
        self.rid = rid

    @property
    def xml(self) -> StartTag:
        extra = {'href': "#" + self.rid} if self.rid else {}
        return StartTag(self.tag, extra)


class Paragraph(MixedParent):
    TAG = 'p'

    def __init__(self, content: MixedContent | str = ""):
        super().__init__(None, content)


class BlockQuote(BiformElement):
    TAG = 'blockquote'

    def __init__(self) -> None:
        super().__init__(None, ArrayContent())


class Preformat(MixedParent):
    TAG = 'pre'

    def __init__(self, content: MixedContent | str = "") -> None:
        super().__init__(None, content)


ElementT = TypeVar('ElementT', bound=Element)


@dataclass
class ItemListElement(Parent[ElementT]):
    _items: list[ElementT | FormatIssueElement]

    def __init__(self, tag: str | None = None, items: Iterable[ElementT] = ()):
        super().__init__(tag)
        self._items = list(items)

    @property
    def content(self) -> ArrayContent:
        return ArrayContent(self._items)

    def __iter__(self) -> Iterator[ElementT]:
        return iter(e for e in self._items if not isinstance(e, FormatIssueElement))

    @property
    def issues(self) -> Iterator[FormatIssue]:
        for child in self._items:
            yield from child.issues

    def append(self, item: ElementT | FormatIssue) -> None:
        if isinstance(item, FormatIssue):
            self.log(item)
        else:
            self._items.append(item)

    def log(self, issue: FormatIssue) -> None:
        self._items.append(FormatIssueElement(issue))

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
    TAG = 'sup'

    def __init__(self, citations: Iterable[Citation] = ()) -> None:
        super().__init__(None, citations)


class ListItem(BiformElement):
    TAG = 'li'

    def __init__(self, content: Iterable[Element] = ()):
        super().__init__(None, ArrayContent(content))


class List(ItemListElement[ListItem]):
    def __init__(self, items: Iterable[ListItem] = (), *, ordered: bool):
        super().__init__('ol' if ordered else 'ul', items)


class DTerm(MixedParent):
    TAG = 'dt'

    def __init__(self, content: MixedContent | str = ""):
        super().__init__(None, content)


class DDefinition(BiformElement):
    TAG = 'dd'

    def __init__(self, content: Iterable[Element] = ()):
        super().__init__(None, content)


class DItem(Element):
    TAG = 'div'

    def __init__(self, term: DTerm, definitions: Iterable[DDefinition] = ()):
        super().__init__(None)
        self.term = term
        self.definitions: MutableSequence[DDefinition] = list(definitions)

    @property
    def content(self) -> ArrayContent:
        return ArrayContent([self.term, *self.definitions])


class TableColumn(HtmlVoidElement):
    TAG = 'col'


class TableColumnGroup(ItemListElement[TableColumn]):
    TAG = 'colgroup'

    def __init__(self) -> None:
        super().__init__()


class TableCell(BiformElement):
    def __init__(self, content: Iterable[Element] = (), *, header: bool):
        super().__init__('th' if header else 'td', content)


class TableRow(ItemListElement[TableCell]):
    TAG = 'tr'

    def __init__(self, cells: Iterable[TableCell] = ()):
        super().__init__(None, cells)


class TableBody(ItemListElement[TableRow]):
    TAG = 'tbody'

    def __init__(self, rows: Iterable[TableRow] = ()):
        super().__init__(None, rows)


class TableHead(ItemListElement[TableRow]):
    TAG = 'thead'

    def __init__(self, rows: Iterable[TableRow] = ()):
        super().__init__(None, rows)


class TableFoot(ItemListElement[TableRow]):
    TAG = 'tfoot'

    def __init__(self, rows: Iterable[TableRow] = ()):
        super().__init__(None, rows)


@dataclass
class Table(Element):
    TAG = 'table'

    colgroups: MutableSequence[TableColumnGroup]
    head: TableHead | None
    bodies: MutableSequence[TableBody]
    foot: TableFoot | None

    def __init__(self) -> None:
        super().__init__()
        self.colgroups = []
        self.head = None
        self.bodies = []
        self.foot = None

    @property
    def content(self) -> ArrayContent:
        ret = MutableArrayContent()
        for cg in self.colgroups:
            ret.append(cg)
        if self.head:
            ret.append(self.head)
        for b in self.bodies:
            ret.append(b)
        if self.foot:
            ret.append(self.foot)
        return ret


@dataclass
class DList(ItemListElement[DItem]):
    TAG = 'dl'

    def __init__(self, items: Iterable[DItem] = ()):
        super().__init__(None, items)


class IssueElement(Element):
    TAG = 'format-issue'

    def __init__(self, msg: str):
        super().__init__(None)
        self.msg = msg
        warn("Construct a FormatIssue and call a log method", DeprecationWarning)

    @property
    def content(self) -> str:
        return self.msg

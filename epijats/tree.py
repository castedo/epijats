from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Generic, Protocol, TYPE_CHECKING, TypeAlias, TypeVar

if TYPE_CHECKING:
    from .typeshed import XmlElement


@dataclass
class StartTag:
    tag: str
    attrib: dict[str, str]

    def __init__(self, tag: str | StartTag, attrib: Mapping[str, str] = {}):
        if isinstance(tag, str):
            self.tag = tag
            self.attrib = dict(attrib)
        else:
            self.tag = tag.tag
            self.attrib = tag.attrib.copy()
            self.attrib.update(attrib)

    @staticmethod
    def from_xml(xe: XmlElement) -> StartTag | None:
        attrib = dict(**xe.attrib)
        return StartTag(xe.tag, attrib) if isinstance(xe.tag, str) else None

    def issubset(self, other: StartTag) -> bool:
        if self.tag != other.tag:
            return False
        for key, value in self.attrib.items():
            if other.attrib.get(key) != value:
                return False
        return True


@dataclass
class PureElement(ABC):
    xml: StartTag

    def __init__(self, xml_tag: str | StartTag):
        self.xml = StartTag(xml_tag)

    @property
    @abstractmethod
    def content(self) -> Content | None: ...


@dataclass
class Element(PureElement):
    _tail: str | None

    def __init__(self, xml_tag: str | StartTag):
        super().__init__(xml_tag)
        self._tail = None

    @property
    def tail(self) -> str | None:
        return self._tail


@dataclass
class Inline(Element):
    def __init__(self, xml_tag: str | StartTag):
        super().__init__(xml_tag)

    @property
    def tail(self) -> str:
        return self._tail or ""

    @tail.setter
    def tail(self, value: str) -> None:
        self._tail = value


@dataclass
class ArrayContent:
    _children: list[PureElement]

    def __init__(self, content: Iterable[PureElement] = ()):
        self._children = list(content)

    def __iter__(self) -> Iterator[PureElement]:
        return iter(self._children)

    def __len__(self) -> int:
        return len(self._children)

    def append(self, e: PureElement) -> None:
        self._children.append(e)

    def extend(self, es: Iterable[PureElement]) -> None:
        self._children.extend(es)

    def just_phrasing(self) -> MixedContent | None:
        solo = self._children[0] if len(self._children) == 1 else None
        if isinstance(solo, MarkupBlock):
            return solo.content
        return None


@dataclass
class MixedContent:
    text: str
    _children: list[Inline]

    def __init__(self, content: str | MixedContent | Iterable[Inline] = ""):
        if isinstance(content, str):
            self.text = content
            self._children = []
        elif isinstance(content, MixedContent):
            self.text = content.text
            self._children = list(content)
        else:
            self.text = ""
            self._children = list(content)

    def __iter__(self) -> Iterator[Inline]:
        return iter(self._children)

    def append(self, e: Inline) -> None:
        self._children.append(e)

    def append_text(self, s: str | None) -> None:
        if s:
            if self._children:
                self._children[-1].tail += s
            else:
                self.text += s

    def empty(self) -> bool:
        return not self._children and not self.text

    def blank(self) -> bool:
        return not self._children and not self.text.strip()


Content: TypeAlias = MixedContent | ArrayContent | str
ContentT = TypeVar('ContentT', MixedContent, ArrayContent, str)
ContentCovT = TypeVar('ContentCovT', covariant=True, bound=Content)
ElementT = TypeVar('ElementT', bound=PureElement)


class Parent(Protocol, Generic[ElementT, ContentCovT]):
    this: ElementT

    @property
    def content(self) -> ContentCovT: ...


@dataclass
class ParentInline(Inline, Parent[Inline, ContentT]):
    _content: ContentT

    def __init__(self, xml_tag: str | StartTag, content: ContentT):
        super().__init__(xml_tag)
        self._content = content
        self.this: Inline = self

    @property
    def content(self) -> ContentT:
        return self._content


@dataclass
class ParentItem(Element, Parent[Element, ContentT]):
    _content: ContentT

    def __init__(self, xml_tag: str | StartTag, content: ContentT):
        super().__init__(xml_tag)
        self._content = content
        self.this: Element = self

    @property
    def content(self) -> ContentT:
        return self._content


class MarkupBlock(ParentItem[MixedContent]):
    """Semantic of HTML div containing only phrasing content"""
    def __init__(self, content: MixedContent | str = ""):
        super().__init__('div', MixedContent(content))


class MarkupElement(ParentInline[MixedContent]):
    def __init__(self, xml_tag: str | StartTag, content: str | MixedContent = ""):
        super().__init__(xml_tag, MixedContent(content))


class DataElement(ParentItem[ArrayContent]):
    def __init__(self, xml_tag: str | StartTag, array: Iterable[PureElement] = ()):
        super().__init__(xml_tag, ArrayContent(array))


class HtmlVoidElement(Inline):
    """HTML void element (such as <br />).

    Only HTML void elements should be serialized in the self-closing XML syntax.
    HTML parsers ignore the XML self-closing tag syntax and parse based
    on a tag name being in a closed fixed list of HTML void elements.
    """

    @property
    def content(self) -> None:
        return None


class WhitespaceElement(Inline):
    """Baseprint XML whitespace-only element.

    To avoid interoperability problems between HTML and XML parsers,
    whitespace-only elements are serialized with a space as content
    to ensure XML parsers do not re-serialize to the self-closing XML syntax.
    """

    @property
    def content(self) -> None:
        return None

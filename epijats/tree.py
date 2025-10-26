from __future__ import annotations

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


class Element(Protocol):
    @property
    def xml(self) -> StartTag: ...

    @property
    def content(self) -> Content | None: ...

    @property
    def is_void(self) -> bool: ...


@dataclass
class ElementBase(Element):
    _xml: StartTag

    def __init__(self, xml_tag: str | StartTag):
        self._xml = StartTag(xml_tag)

    @property
    def xml(self) -> StartTag:
        return self._xml

    @property
    def is_void(self) -> bool:
        return False


class Inline(Element, Protocol):
    @property
    def tail(self) -> str: ...

    @tail.setter
    def tail(self, value: str) -> None: ...


class InlineBase(ElementBase, Inline):
    tail: str = ""

    def __init__(self, xml_tag: str | StartTag):
        super().__init__(xml_tag)


@dataclass
class ArrayContent:
    _children: list[Element]

    def __init__(self, content: Iterable[Element] = ()):
        self._children = list(content)

    def __iter__(self) -> Iterator[Element]:
        return iter(self._children)

    def __len__(self) -> int:
        return len(self._children)

    def append(self, e: Element) -> None:
        self._children.append(e)

    def extend(self, es: Iterable[Element]) -> None:
        self._children.extend(es)

    @property
    def only_child(self) -> Element | None:
        return self._children[0] if len(self._children) == 1 else None


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


@dataclass
class Parent(ElementBase, Generic[ContentT]):
    _content: ContentT

    def __init__(self, xml_tag: str | StartTag, content: ContentT):
        super().__init__(xml_tag)
        self._content = content

    @property
    def content(self) -> ContentT:
        return self._content


class MarkupBlock(Parent[MixedContent]):
    """Semantic of HTML div containing only phrasing content"""

    def __init__(self, content: MixedContent | str = ""):
        super().__init__('div', MixedContent(content))


@dataclass
class MarkupElement(InlineBase):
    _content: MixedContent

    def __init__(self, xml_tag: str | StartTag, content: str | MixedContent = ""):
        super().__init__(xml_tag)
        self._content = MixedContent(content)

    @property
    def content(self) -> MixedContent:
        return self._content


class DataElement(Parent[ArrayContent]):
    def __init__(self, xml_tag: str | StartTag, array: Iterable[Element] = ()):
        super().__init__(xml_tag, ArrayContent(array))


class BiformElement(Parent[ArrayContent]):
    def __init__(self, xml_tag: str | StartTag, array: Iterable[Element] = ()):
        super().__init__(xml_tag, ArrayContent(array))

    @property
    def just_phrasing(self) -> MixedContent | None:
        solo = self.content.only_child
        if isinstance(solo, MarkupBlock):
            return solo.content
        return None


class HtmlVoidInline(InlineBase):
    """HTML void element (such as <br />).

    Only HTML void elements should be serialized in the self-closing XML syntax.
    HTML parsers ignore the XML self-closing tag syntax and parse based
    on a tag name being in a closed fixed list of HTML void elements.
    """

    @property
    def content(self) -> None:
        return None

    @property
    def is_void(self) -> bool:
        return True


class HtmlVoidElement(ElementBase):
    @property
    def content(self) -> None:
        return None

    @property
    def is_void(self) -> bool:
        return True


class WhitespaceElement(InlineBase):
    """Baseprint XML whitespace-only element.

    To avoid interoperability problems between HTML and XML parsers,
    whitespace-only elements are serialized with a space as content
    to ensure XML parsers do not re-serialize to the self-closing XML syntax.
    """

    @property
    def content(self) -> None:
        return None

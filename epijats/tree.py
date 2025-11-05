from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import ClassVar, Generic, TYPE_CHECKING, TypeAlias, TypeVar
from warnings import warn

if TYPE_CHECKING:
    from .typeshed import XmlElement


@dataclass
class StartTag:
    """Immutable start tag (includes attributes)."""

    _name: str
    _attrib: dict[str, str]

    def __init__(self, tag: str | StartTag, attrib: Mapping[str, str] = {}):
        if isinstance(tag, str):
            self._name = tag
            self._attrib = dict(attrib)
        else:
            self._name = tag.name
            self._attrib = tag._attrib.copy()
            self._attrib.update(attrib)

    @property
    def name(self) -> str:
        return self._name

    @property
    def tag(self) -> str:
        return self._name

    @property
    def attrib(self) -> Mapping[str, str]:
        return self._attrib

    @staticmethod
    def from_xml(xe: XmlElement) -> StartTag | None:
        attrib = dict(**xe.attrib)
        return StartTag(xe.tag, attrib) if isinstance(xe.tag, str) else None

    def issubset(self, x: StartTag | XmlElement) -> bool:
        other = x if isinstance(x, StartTag) else StartTag.from_xml(x)
        if other is None or self.name != other.name:
            return False
        for key, value in self.attrib.items():
            if other.attrib.get(key) != value:
                return False
        return True


@dataclass
class Element(ABC):
    TAG: ClassVar[str | StartTag]

    _tag: StartTag

    def __init__(self, tag: str | StartTag | None = None):
        class_tag = getattr(self.__class__, 'TAG', None)
        if class_tag:
            if tag:
                warn(f"{self.__class__.__name__} tag argument ignored")
            self._tag = StartTag(class_tag)
        else:
            if not tag:
                raise ValueError("Missing element tag")
            self._tag = StartTag(tag)

    @property
    def tag(self) -> StartTag:
        return self._tag

    def set_attrib(self, key: str, value: str) -> None:
        if key in self.tag.attrib:
            raise KeyError
        self._tag._attrib[key] = value

    @property
    def xml(self) -> StartTag:
        return self.tag

    @property
    def xml_attrib(self) -> Mapping[str, str]:
        return self.tag.attrib

    @property
    @abstractmethod
    def content(self) -> Content | None: ...

    @property
    def is_void(self) -> bool:
        return False


MixedSink: TypeAlias = Callable[[str | Element], None]


@dataclass
class ArrayContent:
    _children: list[Element]

    def __init__(self, content: Iterable[Element] = ()):
        self._children = list(content)

    def __iter__(self) -> Iterator[Element]:
        return iter(self._children)

    def __len__(self) -> int:
        return len(self._children)

    @property
    def only_child(self) -> Element | None:
        return self._children[0] if len(self._children) == 1 else None

    def append(self, a: Element) -> None:
        warn("Use MutableArrayContent", DeprecationWarning)
        self._children.append(a)


class MutableArrayContent(ArrayContent):
    def append(self, e: Element) -> None:
        self._children.append(e)

    def __call__(self, a: Element) -> None:
        self.append(a)


@dataclass
class MixedContent:
    text: str
    _children: list[tuple[Element, str]]

    def __init__(self, content: MixedContent | str = ""):
        warn("Use MutableMixedContent", DeprecationWarning)
        if isinstance(content, str):
            self.text = content
            self._children = []
        else:
            self.text = content.text
            self._children = list(content._children)

    def __iter__(self) -> Iterator[tuple[Element, str]]:
        return iter(self._children)

    def empty(self) -> bool:
        return not self._children and not self.text

    def blank(self) -> bool:
        return not self._children and not self.text.strip()


class MutableMixedContent(MixedContent):
    def __init__(self, content: MixedContent | str = ""):
        if isinstance(content, str):
            self.text = content
            self._children = []
        elif isinstance(content, MixedContent):
            self.text = content.text
            self._children = list(content)
        else:
            self.text = ""
            self._children = list(content)

    def append(self, a: str | Element) -> None:
        if isinstance(a, str):
            if self._children:
                end = self._children[-1]
                self._children[-1] = (end[0], end[1] + a)
            else:
                self.text += a
        else:
            self._children.append((a, ""))

    def __call__(self, a: str | Element) -> None:
        self.append(a)


Content: TypeAlias = str | ArrayContent | MixedContent
AppendT = TypeVar('AppendT')
AppendCovT = TypeVar('AppendCovT', covariant=True)
AppendConT = TypeVar('AppendConT', contravariant=True)


class Parent(Element, Generic[AppendConT]):
    @abstractmethod
    def append(self, a: AppendConT) -> None: ...


class ArrayParent(Parent[Element]):
    _content: MutableArrayContent

    def __init__(self, tag: str | StartTag | None, content: Iterable[Element] = ()):
        super().__init__(tag)
        self._content = MutableArrayContent(content)

    @property
    def content(self) -> ArrayContent:
        return self._content

    def append(self, a: Element) -> None:
        self._content.append(a)


@dataclass
class MixedParent(Parent[str | Element]):
    _content: MutableMixedContent

    def __init__(self, tag: str | StartTag | None, content: MixedContent | str = ""):
        super().__init__(tag)
        self._content = MutableMixedContent(content)

    @property
    def content(self) -> MixedContent:
        return self._content

    def append(self, a: str | Element) -> None:
        self._content(a)


class MarkupBlock(MixedParent):
    """Semantic of HTML div containing only phrasing content"""

    TAG = 'div'

    def __init__(self, content: MixedContent | str = ""):
        super().__init__(None, content)


class MarkupInline(MixedParent):
    "General purpose public DOM API class for inline elements like <b>, <i>, etc..."


class MarkupElement(MixedParent):
    def __init__(self, xml_tag: str | StartTag, content: MixedContent | str = ""):
        super().__init__(xml_tag, content)
        warn("Use MarkupInline", DeprecationWarning)


class BiformElement(ArrayParent):
    def __init__(self, tag: str | StartTag | None, array: Iterable[Element] = ()):
        super().__init__(tag, array)

    @property
    def just_phrasing(self) -> MixedContent | None:
        solo = self.content.only_child
        if isinstance(solo, MarkupBlock):
            return solo.content
        return None


class HtmlVoidElement(Element):
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


class WhitespaceElement(Element):
    """Baseprint XML whitespace-only element.

    To avoid interoperability problems between HTML and XML parsers,
    whitespace-only elements are serialized with a space as content
    to ensure XML parsers do not re-serialize to the self-closing XML syntax.
    """

    @property
    def content(self) -> None:
        return None

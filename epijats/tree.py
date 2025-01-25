from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator, Literal


@dataclass
class StartTag:
    tag: str
    attrib: dict[str, str] = field(default_factory=dict)


@dataclass
class ElementContent:
    text: str
    _subelements: list[SubElement | DataSubElement]
    data_model: bool

    def __init__(self, text: str = "", elements: Iterable[SubElement] = []):
        self.text = text
        self._subelements = list(elements)
        self.data_model = False

    def __iter__(self) -> Iterator[SubElement | DataSubElement]:
        return iter(self._subelements)

    def append(self, e: SubElement) -> None:
        self._subelements.append(e)

    def append_text(self, s: str | None) -> None:
        if s:
            if self._subelements:
                self._subelements[-1].tail += s
            else:
                self.text += s

    def empty(self) -> bool:
        return not self.text and not self._subelements


@dataclass
class MixedContent:
    text: str
    _children: list[MarkupSubElement | DataSubElement]
    data_model: bool

    def __init__(self, text: str = "", elements: Iterable[MarkupSubElement] = []):
        self.text = text
        self._children = list(elements)
        self.data_model = False

    def __iter__(self) -> Iterator[MarkupSubElement | DataSubElement]:
        return iter(self._children)

    def append(self, e: MarkupSubElement | DataSubElement) -> None:
        self._children.append(e)


@dataclass
class Element:
    xml: StartTag
    html: StartTag | None
    block_level: bool

    def __init__(self, xml_stag: StartTag):
        self.xml = xml_stag
        self.html = None
        self.block_level = False


@dataclass
class SubElement(Element):
    content: ElementContent
    tail: str

    def __init__(self, xml_tag: str, text: str = ""):
        super().__init__(StartTag(xml_tag))
        self.content = ElementContent(text)
        self.tail = ""

    @property
    def data_model(self) -> bool:
        return self.content.data_model


@dataclass
class MarkupElement(Element):
    content: MixedContent

    def __init__(self, xml_tag: str, xml_attrib: dict[str, str] = {}, text: str = ""):
        super().__init__(StartTag(xml_tag, xml_attrib))
        self.content = MixedContent(text)


@dataclass
class MarkupSubElement(Element):
    tail: str
    content: MixedContent

    def __init__(
        self,
        xml_tag: str,
        text: str = "",
    ):
        super().__init__(StartTag(xml_tag))
        self.tail = ""
        self.content = MixedContent(text)

    @property
    def data_model(self) -> Literal[False]:
        return False


@dataclass
class DataElement(Element):
    _children: list[DataElement | MarkupElement]

    def __init__(
        self,
        xml_tag: str,
        xml_attrib: dict[str, str] = {},
        children: list[DataElement | MarkupElement] = [],
    ):
        super().__init__(StartTag(xml_tag, xml_attrib))
        self._children = list(children)

    def __iter__(self) -> Iterator[DataElement | MarkupElement]:
        return iter(self._children)

    def append(self, e: DataElement | MarkupElement) -> None:
        self._children.append(e)

    def has_block_level_markup(self) -> bool:
        return any(c.block_level for c in self)

    @property
    def data_model(self) -> Literal[True]:
        return True


@dataclass
class DataSubElement(DataElement):
    tail: str

    def __init__(
        self,
        xml_tag: str,
        xml_attrib: dict[str, str] = {},
    ):
        super().__init__(xml_tag, xml_attrib)
        self.tail = ""


def make_paragraph(text: str) -> SubElement:
    ret = SubElement('p', text)
    ret.html = StartTag('p')
    return ret

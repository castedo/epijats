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

    def extend(self, es: Iterator[SubElement]) -> None:
        self._subelements.extend(es)

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

    def __init__(self, text: str = ""):
        self.text = text
        self._children = []

    def __iter__(self) -> Iterator[MarkupSubElement | DataSubElement]:
        return iter(self._children)

    def append(self, e: MarkupSubElement | DataSubElement) -> None:
        self._children.append(e)


@dataclass
class SubElement:
    xml: StartTag
    html: StartTag | None
    content: ElementContent
    block_level: bool
    tail: str

    def __init__(
        self,
        text: str,
        elements: Iterable[SubElement],
        xml_tag: str,
        tail: str = "",
    ):
        self.xml = StartTag(xml_tag)
        self.html = None
        self.content = ElementContent(text, elements)
        self.block_level = False
        self.tail = tail

    @property
    def data_model(self) -> bool:
        return self.content.data_model


@dataclass
class MarkupElement:
    xml: StartTag
    html: StartTag | None
    content: MixedContent
    block_level: bool

    def __init__(
        self,
        xml_tag: str,
        xml_attrib: dict[str, str] = {},
        text: str = "",
    ):
        self.xml = StartTag(xml_tag, xml_attrib)
        self.html = None
        self.content = MixedContent(text)
        self.block_level = False


@dataclass
class MarkupSubElement(MarkupElement):
    tail: str

    def __init__(
        self,
        xml_tag: str,
        xml_attrib: dict[str, str] = {},
        text: str = "",
    ):
        super().__init__(xml_tag, xml_attrib, text)
        self.tail = ""


@dataclass
class DataElement:
    xml: StartTag
    html: StartTag | None
    _children: list[DataElement | MarkupElement]

    def __init__(
        self,
        xml_tag: str,
        xml_attrib: dict[str, str] = {},
        children: list[DataElement | MarkupElement] = [],
    ):
        self.xml = StartTag(xml_tag, xml_attrib)
        self._children = list(children)

    def __iter__(self) -> Iterator[DataElement | MarkupElement]:
        return iter(self._children)

    def append(self, e: DataElement | MarkupElement) -> None:
        self._children.append(e)

    def has_block_level_markup(self) -> bool:
        return any(isinstance(c, MarkupElement) and c.block_level for c in self)

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
    ret = SubElement(text, [], 'p')
    ret.html = StartTag('p')
    return ret

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator, Literal


@dataclass
class StartTag:
    tag: str
    attrib: dict[str, str] = field(default_factory=dict)


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

    def append_text(self, s: str | None) -> None:
        if s:
            if self._children:
                self._children[-1].tail += s
            else:
                self.text += s

    def empty(self) -> bool:
        return not self.text and not self._children

ElementContent = MixedContent


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
    tail: str

    def __init__(self, xml_tag: str):
        super().__init__(StartTag(xml_tag))
        self.tail = ""


@dataclass
class MarkupElement(Element):
    content: MixedContent

    def __init__(self, xml_tag: str, xml_attrib: dict[str, str] = {}, text: str = ""):
        super().__init__(StartTag(xml_tag, xml_attrib))
        self.content = MixedContent(text)


@dataclass
class MarkupSubElement(SubElement):
    content: MixedContent

    def __init__(
        self,
        xml_tag: str,
        text: str = "",
    ):
        super().__init__(xml_tag)
        self.content = MixedContent(text)

    @property
    def data_model(self) -> bool:
        return self.content.data_model


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


def make_paragraph(text: str) -> MarkupSubElement:
    ret = MarkupSubElement('p', text)
    ret.html = StartTag('p')
    return ret

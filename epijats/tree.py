from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator


@dataclass
class ElementContent:
    text: str
    _subelements: list[SubElement]

    def __init__(self, text: str = "", elements: Iterable[SubElement] = []):
        self.text = text
        self._subelements = list(elements)
        self.data_model = False

    def __iter__(self) -> Iterator[SubElement]:
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
class SubElement(ElementContent):
    xml_tag: str
    tail: str

    def __init__(
        self,
        text: str,
        elements: Iterable[SubElement],
        xml_tag: str,
        tail: str,
    ):
        super().__init__(text, elements)
        self.xml_tag = xml_tag
        self.tail = tail

    @property
    def xml_attrib(self) -> dict[str, str]:
        return {}


@dataclass
class CommonElement(SubElement):
    """Common JATS/HTML element"""
    html_tag: str

    def __init__(
        self,
        text: str,
        elements: Iterable[SubElement],
        xml_tag: str,
        html_tag: str,
        tail: str,
    ):
        super().__init__(text, elements, xml_tag, tail)
        self.xml_tag = xml_tag
        self.html_tag = html_tag
        self.html_tag = html_tag
        self.tail = tail

    @property
    def html_attrib(self) -> dict[str, str]:
        return {}


@dataclass
class Element:
    xml_tag: str
    xml_attrib: dict[str, str] = field(default_factory=dict)


@dataclass
class MarkupElement(Element):
    text: str = ""
    _children: list[MarkupSubElement | DataSubElement] = field(default_factory=list)
    block_level = False

    def __iter__(self) -> Iterator[MarkupSubElement | DataSubElement]:
        return iter(self._children)

    def append(self, e: MarkupSubElement | DataSubElement) -> None:
        self._children.append(e)


@dataclass
class MarkupSubElement(MarkupElement):
    tail: str = ""


@dataclass
class DataElement(Element):
    _children: list[DataElement | MarkupElement] = field(default_factory=list)

    def __iter__(self) -> Iterator[DataElement | MarkupElement]:
        return iter(self._children)

    def append(self, e: DataElement | MarkupElement) -> None:
        self._children.append(e)

    def has_block_level_markup(self) -> bool:
        return any(isinstance(c, MarkupElement) and c.block_level for c in self)


@dataclass
class DataSubElement(DataElement):
    tail: str = ""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class Element:
    xml_tag: str
    xml_attrib: dict[str, str] = field(default_factory=dict)


@dataclass
class MarkupElement(Element):
    text: str = ""
    _children: list[MarkupSubElement | DataSubElement] = field(default_factory=list)

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
    indent: bool = True

    def __iter__(self) -> Iterator[DataElement | MarkupElement]:
        return iter(self._children)

    def append(self, e: DataElement | MarkupElement) -> None:
        self._children.append(e)


@dataclass
class DataSubElement(DataElement):
    tail: str = ""

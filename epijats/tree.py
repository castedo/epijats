from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class Base:
    xml_tag: str
    xml_attrib: dict[str, str] = field(default_factory=dict)


@dataclass
class MarkupContent(Base):
    text: str = ""
    _children: list[MarkupElement] = field(default_factory=list)

    def __iter__(self) -> Iterator[MarkupElement]:
        return iter(self._children)

    def append(self, e: MarkupElement) -> None:
        self._children.append(e)


@dataclass
class MarkupElement(MarkupContent):
    tail: str = ""


@dataclass
class DataContent(Base):
    _children: list[DataContent | MarkupContent] = field(default_factory=list)

    def __iter__(self) -> Iterator[DataContent | MarkupContent]:
        return iter(self._children)

    def append(self, e: DataContent | MarkupContent) -> None:
        self._children.append(e)

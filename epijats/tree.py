from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, TYPE_CHECKING, TypeAlias


@dataclass
class StartTag:
    tag: str
    attrib: dict[str, str]

    def __init__(self, tag: str | StartTag, attrib: dict[str, str] = {}):
        if isinstance(tag, str):
            self.tag = tag
            self.attrib = attrib
        else:
            self.tag = tag.tag
            self.attrib = tag.attrib | attrib


@dataclass
class Element:
    xml: StartTag
    html: StartTag | None
    tail: str
    block_level: bool

    def __init__(self, xml_tag: str | StartTag):
        self.xml = StartTag(xml_tag)
        self.html = None
        self.tail = ""
        self.block_level = False

    def __iter__(self) -> Iterator[Element]:
        return iter(())

    def has_block_level_markup(self) -> bool:
        return any(c.block_level for c in self)


if TYPE_CHECKING:
    ArrayContent: TypeAlias = list[Element]


@dataclass
class MixedContent:
    text: str
    _children: ArrayContent

    def __init__(self, text: str = ""):
        super().__init__()
        self.text = text
        self._children = []

    def __iter__(self) -> Iterator[Element]:
        return iter(self._children)

    def append(self, e: Element) -> None:
        self._children.append(e)

    def append_text(self, s: str | None) -> None:
        if s:
            if self._children:
                self._children[-1].tail += s
            else:
                self.text += s

    def empty(self) -> bool:
        return not self.text and not self._children


@dataclass
class MarkupElement(Element):
    content: MixedContent

    def __init__(self, xml_tag: str | StartTag, text: str = ""):
        super().__init__(xml_tag)
        self.content = MixedContent(text)


@dataclass
class DataElement(Element):
    array: list[Element]

    def __init__(
        self,
        xml_tag: str | StartTag,
        array: list[Element] = [],
    ):
        super().__init__(xml_tag)
        self.array = list(array)

    def __iter__(self) -> Iterator[Element]:
        return iter(self.array)

    def append(self, e: Element) -> None:
        self.array.append(e)


def make_paragraph(text: str) -> MarkupElement:
    ret = MarkupElement('p', text)
    ret.html = StartTag('p')
    ret.block_level = True
    return ret

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass
class StartTag:
    tag: str
    attrib: dict[str, str]

    def __init__(self, tag: str | StartTag, attrib: dict[str, str] = {}):
        if isinstance(tag, str):
            self.tag = tag
            self.attrib = attrib.copy()
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


@dataclass
class MixedContent:
    text: str
    _children: list[Element]

    def __init__(self, content: str | MixedContent = ""):
        super().__init__()
        if isinstance(content, str):
            self.text = content
            self._children = []
        else:
            self.text = content.text
            self._children = list(content)

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
        return not self._children and not self.text

    def empty_or_ws(self) -> bool:
        return not self._children and not self.text.strip()


@dataclass
class MarkupElement(Element):
    _content: MixedContent

    def __init__(self, xml_tag: str | StartTag, content: str | MixedContent = ""):
        super().__init__(xml_tag)
        self._content = MixedContent(content)

    @property
    def content(self) -> MixedContent:
        return self._content

@dataclass
class DataElement(Element):
    _array: list[Element]

    def __init__(
        self,
        xml_tag: str | StartTag,
        array: list[Element] = [],
    ):
        super().__init__(xml_tag)
        self._array = list(array)

    def __iter__(self) -> Iterator[Element]:
        return iter(self._array)

    def append(self, e: Element) -> None:
        self._array.append(e)


def make_paragraph(text: str) -> MarkupElement:
    ret = MarkupElement('p', text)
    ret.html = StartTag('p')
    ret.block_level = True
    return ret

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from lxml.builder import ElementMaker

if TYPE_CHECKING:
    from lxml.etree import _Element

from .tree import DataElement, Element, MarkupElement, MixedContent


class ElementFormatter(ABC):
    @abstractmethod
    def make_element(self, src: Element) -> _Element: ...

    def markup_content(self, src: MixedContent, dest: _Element) -> None:
        dest.text = src.text
        for it in src:
            sub = self.make_element(it)
            if isinstance(it, MarkupElement):
                self.markup_content(it.content, sub)
                sub.tail = it.tail
            else:
                self.data_content(it, sub, 0)
                sub.tail = "\n"
            dest.append(sub)

    def data_content(self, src: Element, dest: _Element, level: int) -> None:
        dest.text = "\n" + "  " * level
        presub = "\n"
        if not src.has_block_level_markup():
            presub += "  " * (level + 1)
        sub: _Element | None = None
        for it in src:
            sub = self.make_element(it)
            if isinstance(it, MarkupElement):
                self.markup_content(it.content, sub)
            else:
                self.data_content(it, sub, level + 1)
            sub.tail = presub
            dest.append(sub)
        if sub is not None:
            sub.tail = dest.text
            dest.text = presub


class XmlFormatter(ElementFormatter):
    def __init__(self, *, nsmap: dict[str, str]):
        self.EM = ElementMaker(nsmap=nsmap)

    def make_element(self, src: Element) -> _Element:
        return self.EM(src.xml.tag, **src.xml.attrib)


XML = XmlFormatter(
    nsmap={
        'ali': "http://www.niso.org/schemas/ali/1.0",
        'mml': "http://www.w3.org/1998/Math/MathML",
        'xlink': "http://www.w3.org/1999/xlink",
    }
)


def markup_element(src: MarkupElement) -> _Element:
    ret = XML.make_element(src)
    XML.markup_content(src.content, ret)
    return ret


def data_element(src: DataElement, level: int) -> _Element:
    ret = XML.make_element(src)
    XML.data_content(src, ret, level)
    return ret

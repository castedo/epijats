from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from lxml.builder import ElementMaker

if TYPE_CHECKING:
    from lxml.etree import _Element

from .tree import Element, MarkupElement, MixedContent


class ElementFormatter(ABC):
    @abstractmethod
    def start_element(self, src: Element) -> _Element: ...

    def copy_content(self, src: Element, dest: _Element, level: int) -> None:
        if isinstance(src, MarkupElement):
            self._markup_content(src.content, dest, level)
        else:
            self._data_content(src, dest, level)

    def _markup_content(self, src: MixedContent, dest: _Element, level: int) -> None:
        dest.text = src.text
        for it in src:
            sub = self.start_element(it)
            sublevel = level if isinstance(it, MarkupElement) else level + 1
            self.copy_content(it, sub, sublevel)
            sub.tail = it.tail
            dest.append(sub)

    def _data_content(self, src: Element, dest: _Element, level: int) -> None:
        dest.text = "\n" + "  " * level
        presub = "\n" + ("  " * (level + 1))
        sub: _Element | None = None
        for it in src:
            sub = self.start_element(it)
            self.copy_content(it, sub, level + 1)
            sub.tail = presub
            dest.append(sub)
        if sub is not None:
            sub.tail = dest.text
            dest.text = presub


class XmlFormatter(ElementFormatter):
    def __init__(self, *, nsmap: dict[str, str]):
        self.EM = ElementMaker(nsmap=nsmap)

    def start_element(self, src: Element) -> _Element:
        return self.EM(src.xml.tag, **src.xml.attrib)


XML = XmlFormatter(
    nsmap={
        'ali': "http://www.niso.org/schemas/ali/1.0/",
        'mml': "http://www.w3.org/1998/Math/MathML",
        'xlink': "http://www.w3.org/1999/xlink",
    }
)


def xml_element(src: Element) -> _Element:
    ret = XML.start_element(src)
    XML.copy_content(src, ret, 0)
    return ret

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import cast

from lxml.builder import ElementMaker
from lxml.etree import CDATA, _Element

from .tree import CdataElement, CitationTuple, Element, MarkupElement


class ElementFormatter(ABC):
    @abstractmethod
    def __call__(self, src: Element, level: int) -> _Element: ...


class MarkupFormatter:
    def __init__(self, sub: ElementFormatter):
        self.subformat = sub

    def format_content(self, src: MarkupElement, level: int, dest: _Element) -> None:
        dest.text = src.content.text
        for it in src.content:
            sublevel = level if isinstance(it, MarkupElement) else level + 1
            sub = self.subformat(it, sublevel)
            sub.tail = it.tail
            dest.append(sub)


class IndentFormatter:
    def __init__(self, sub: ElementFormatter, sep: str = ''):
        self.subformat = sub
        self.sep = sep

    def format_content(self, src: Element, level: int, dest: _Element) -> None:
        last_newline = "\n" + "  " * level
        newline = "\n" + ("  " * (level + 1))
        sub: _Element | None = None
        for it in src:
            sub = self.subformat(it, level + 1)
            sub.tail = self.sep + newline 
            dest.append(sub)
        if sub is None:
            dest.text = last_newline
        else:
            dest.text = newline
            sub.tail = last_newline


class CommonContentFormatter:
    def __init__(self, sub: ElementFormatter) -> None:
        self.markup = MarkupFormatter(sub)
        self.default = IndentFormatter(sub)

    def format_content(self, src: Element, level: int, dest: _Element) -> None:
        if isinstance(src, MarkupElement):
            self.markup.format_content(src, level, dest)
        else:
            self.default.format_content(src, level, dest)


class XmlFormatter(ElementFormatter):
    def __init__(self, *, nsmap: dict[str, str]):
        self.EM = ElementMaker(nsmap=nsmap)
        self.citation = IndentFormatter(self, sep=",")
        self.common = CommonContentFormatter(self)

    def __call__(self, src: Element, level: int) -> _Element:
        ret = self.EM(src.xml.tag, src.xml.attrib)
        if isinstance(src, CdataElement):
            ret.text = cast(str, CDATA(src.content))
        elif isinstance(src, CitationTuple):
            self.citation.format_content(src, level, ret)
        else:
            self.common.format_content(src, level, ret)
        return ret


XML = XmlFormatter(
    nsmap={
        'ali': "http://www.niso.org/schemas/ali/1.0/",
        'mml': "http://www.w3.org/1998/Math/MathML",
        'xlink': "http://www.w3.org/1999/xlink",
    }
)


def xml_element(src: Element) -> _Element:
    return XML(src, 0)

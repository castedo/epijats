from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TYPE_CHECKING, TypeAlias, cast

from .tree import (
    CdataElement,
    CitationTuple,
    Element,
    MarkupElement,
    MixedContent,
    PureElement,
)

if TYPE_CHECKING:
    import lxml.etree

    XmlElement: TypeAlias = lxml.etree._Element


class ElementFormatter(Protocol):
    def format(self, src: PureElement, level: int) -> Iterable[XmlElement]: ...


def append_content(src: str, dest: XmlElement) -> None:
    if src:
        if len(dest):
            last = dest[-1]
            last.tail = src if last.tail is None else last.tail + src
        else:
            dest.text = src if dest.text is None else dest.text + src


class MarkupFormatter:
    def __init__(self, sub: ElementFormatter):
        self.sub = sub

    def format(self, src: MixedContent, level: int, dest: XmlElement) -> None:
        dest.text = src.text
        for it in src:
            sublevel = level if isinstance(it, MarkupElement) else level + 1
            for sub in self.sub.format(it, sublevel):
                dest.append(sub)
            append_content(it.tail, dest)


class IndentFormatter:
    def __init__(self, sub: ElementFormatter, sep: str = ''):
        self.sub = sub
        self.sep = sep

    def format_content(self, src: PureElement, level: int, dest: XmlElement) -> None:
        assert not isinstance(src, MarkupElement)
        last_newline = "\n" + "  " * level
        newline = "\n" + ("  " * (level + 1))
        sub: XmlElement | None = None
        for it in src:
            for sub in self.sub.format(it, level + 1):
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

    def format_content(self, src: PureElement, level: int, dest: XmlElement) -> None:
        if isinstance(src, MarkupElement):
            self.markup.format(src.content, level, dest)
        else:
            self.default.format_content(src, level, dest)


class XmlFormatter(ElementFormatter):
    def __init__(self, *, nsmap: dict[str, str]):
        self.nsmap = nsmap
        self.citation = IndentFormatter(self, sep=",")
        self.common = CommonContentFormatter(self)

    def to_one_only(self, src: PureElement, level: int) -> XmlElement:
        import lxml.etree

        ret = lxml.etree.Element(src.xml.tag, src.xml.attrib, nsmap=self.nsmap)
        if isinstance(src, CdataElement):
            ret.text = cast(str, lxml.etree.CDATA(src.content))
        elif isinstance(src, CitationTuple):
            self.citation.format_content(src, level, ret)
        else:
            self.common.format_content(src, level, ret)
        return ret

    def root(self, src: PureElement) -> XmlElement:
        return self.to_one_only(src, 0)

    def format(self, src: PureElement, level: int) -> Iterable[XmlElement]:
        return [self.to_one_only(src, level)]


XML = XmlFormatter(
    nsmap={
        'ali': "http://www.niso.org/schemas/ali/1.0/",
        'mml': "http://www.w3.org/1998/Math/MathML",
        'xlink': "http://www.w3.org/1999/xlink",
    }
)


def xml_element(src: Element) -> XmlElement:
    return XML.root(src)

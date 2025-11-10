from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, TYPE_CHECKING
from warnings import warn

import xml.etree.ElementTree

from ..parse.baseprint import get_ET
from ..elements import CitationTuple
from ..tree import (
    ArrayContent,
    BiformElement,
    FormatIssueElement,
    MixedContent,
    Element,
    WhitespaceElement,
)


if TYPE_CHECKING:
    from ..typeshed import XmlElement


class ElementFormatter(Protocol):
    def format(self, src: Element, level: int) -> Iterator[XmlElement]: ...


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
        for element, tail in src:
            sublevel = level if isinstance(element.content, MixedContent) else level + 1
            for sub in self.sub.format(element, sublevel):
                dest.append(sub)  # type: ignore[arg-type]
            append_content(tail, dest)
        if not dest.text and not len(dest):
            msg = "Space inserted into otherwise empty {} element"
            warn(msg.format(dest.tag))
            # Markup elements with literally an empty string are not supported.
            # Space is inserted to ensure XML parsers do not convert a mixed content
            # element to a self-closing XML tag. Mixed content elements are not HTML
            # void elements. To be compatible with HTML parsers, only HTML void elements
            # can use the self-closing XML tag syntax.
            dest.text = ' '


class InlineListFormatter:
    def __init__(self, sub: ElementFormatter, *, sep: str = ''):
        self.sub = sub
        self.sep = sep

    def format(self, src: ArrayContent, level: int, dest: XmlElement) -> None:
        sub: XmlElement | None = None
        todo = list(src)
        while todo:
            it = todo.pop(0)
            sublevel = level if isinstance(it.content, MixedContent) else level + 1
            for sub in self.sub.format(it, sublevel):
                if todo:
                    sub.tail = self.sep
                dest.append(sub)  # type: ignore[arg-type]


class IndentFormatter:
    def __init__(self, sub: ElementFormatter, sep: str = ''):
        self.sub = sub
        self.sep = sep

    def format(self, src: ArrayContent, level: int, dest: XmlElement) -> None:
        last_newline = "\n" + "  " * level
        newline = "\n" + ("  " * (level + 1))
        sub: XmlElement | None = None
        for it in src:
            for sub in self.sub.format(it, level + 1):
                sub.tail = self.sep + newline
                dest.append(sub)  # type: ignore[arg-type]
        if sub is None:
            dest.text = last_newline
        else:
            dest.text = newline
            sub.tail = last_newline


class CommonContentFormatter:
    def __init__(self, sub: ElementFormatter) -> None:
        self.markup = MarkupFormatter(sub)
        self.default = IndentFormatter(sub)

    def format_content(self, src: Element, level: int, dest: XmlElement) -> None:
        if isinstance(src.content, str):
            dest.text = src.content
        elif isinstance(src, BiformElement):
            if src.just_phrasing is not None:
                self.markup.format(src.just_phrasing, level, dest)
            elif len(src.content) == 0:
                dest.text = ' '
            else:
                self.default.format(src.content, level, dest)
        elif isinstance(src.content, ArrayContent):
            self.default.format(src.content, level, dest)
        elif isinstance(src.content, MixedContent):
            self.markup.format(src.content, level, dest)
        elif src.is_void:
            # HTML void elements must be self-closing and all others not,
            # for compatibility with HTML parsers.
            dest.text = None
        else:
            if not isinstance(src, WhitespaceElement):
                warn(f"Unknown element {src.tag.name} wihtout content")
            # For interop with both XML and HTML parsers,
            # a space will prevent XML parsers from converting a Baseprint XML
            # whitespace-only element to a self-closing XML tag.
            dest.text = ' '


def root_namespaces(src: XmlElement) -> XmlElement:
    ret = src
    if not isinstance(src, xml.etree.ElementTree.Element):
        import lxml.etree

        nsmap = dict[str | None, str]()
        for c in src.iter():
            nsmap.update(c.nsmap)
        ret = lxml.etree.Element(src.tag, src.attrib, nsmap=nsmap)
        ret.text = src.text
        for c in src:
            ret.append(c)
    return ret


class XmlFormatter(ElementFormatter):
    def __init__(self, *, use_lxml: bool = False):
        self.citation = InlineListFormatter(self, sep=",")
        self.common = CommonContentFormatter(self)
        if use_lxml:
            warn("lxml specific output will be removed.", DeprecationWarning)
        self.ET = get_ET(use_lxml=use_lxml)

    def to_one_only(self, src: Element, level: int) -> XmlElement:
        ret: XmlElement = self.ET.Element(src.tag.name, src.xml.attrib)
        if isinstance(src, CitationTuple):
            self.citation.format(src.content, level, ret)
        else:
            self.common.format_content(src, level, ret)
        return ret

    def root(self, src: Element) -> XmlElement:
        return root_namespaces(self.to_one_only(src, 0))

    def format(self, src: Element, level: int) -> Iterator[XmlElement]:
        if isinstance(src, FormatIssueElement):
            return iter(())
        return iter((self.to_one_only(src, level),))

    def to_str(self, src: Element) -> str:
        e = self.root(src)
        return self.ET.tostring(e).decode()  # type: ignore[no-any-return]

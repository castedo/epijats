from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TYPE_CHECKING, TypeAlias
import xml.etree.ElementTree

from .tree import (
    CitationTuple,
    EmptyElement,
    MarkupElement,
    MixedContent,
    PureElement,
)


if TYPE_CHECKING:
    from types import ModuleType
    import lxml.etree

    XmlElement: TypeAlias = lxml.etree._Element | xml.etree.ElementTree.Element


NAMESPACE_MAP = {
    'ali': "http://www.niso.org/schemas/ali/1.0/",
    'mml': "http://www.w3.org/1998/Math/MathML",
    'xlink': "http://www.w3.org/1999/xlink",
}


# key is (use_lxml: bool)
_NAMESPACES_REGISTERED = {False: False, True: False}


def get_ET(*, use_lxml: bool) -> ModuleType:
    ret: ModuleType
    if use_lxml:
        import lxml.etree

        ret = lxml.etree
    else:
        ret = xml.etree.ElementTree

    if not _NAMESPACES_REGISTERED[use_lxml]:
        for prefix, name in NAMESPACE_MAP.items():
            ret.register_namespace(prefix, name)
        _NAMESPACES_REGISTERED[use_lxml] = True
    return ret


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
                dest.append(sub)  # type: ignore[arg-type]
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

    def format_content(self, src: PureElement, level: int, dest: XmlElement) -> None:
        if isinstance(src, MarkupElement):
            self.markup.format(src.content, level, dest)
        elif not isinstance(src, EmptyElement):
            self.default.format_content(src, level, dest)


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
    def __init__(self, *, use_lxml: bool):
        self.citation = IndentFormatter(self, sep=",")
        self.common = CommonContentFormatter(self)
        self.ET = get_ET(use_lxml=use_lxml)

    def to_one_only(self, src: PureElement, level: int) -> XmlElement:
        ret: XmlElement = self.ET.Element(src.xml.tag, src.xml.attrib)
        if isinstance(src, CitationTuple):
            self.citation.format_content(src, level, ret)
        else:
            self.common.format_content(src, level, ret)
        return ret

    def root(self, src: PureElement) -> XmlElement:
        return root_namespaces(self.to_one_only(src, 0))

    def format(self, src: PureElement, level: int) -> Iterable[XmlElement]:
        return [self.to_one_only(src, level)]

    def to_str(self, src: PureElement) -> str:
        e = self.root(src)
        return self.ET.tostring(e).decode()  # type: ignore[no-any-return]

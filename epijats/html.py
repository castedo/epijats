from __future__ import annotations

from typing import TYPE_CHECKING

from lxml.html import HtmlElement, tostring
from lxml.html.builder import E

from .baseprint import ProtoSection
from .tree import Element, MixedContent, MarkupElement
from .xml import ElementFormatter

if TYPE_CHECKING:
    from lxml.etree import _Element


def _html_to_str(*ins: str | HtmlElement) -> str:
    ss = [x if isinstance(x, str) else tostring(x).decode() for x in ins]
    return "".join(ss)


class HtmlGenerator(ElementFormatter):
    def make_element(self, src: Element) -> _Element:
        return self.make_html_element(src)

    def make_html_element(self, src: Element) -> HtmlElement:
        if src.html is None:
            raise ValueError
        return E(src.html.tag, **src.html.attrib)

    def content_to_str(self, src: MixedContent) -> str:
        return _html_to_str(*self._content(src))

    def proto_section_to_str(self, src: ProtoSection) -> str:
        return _html_to_str(*self._proto_section_content(src))

    def _content(self, src: MixedContent) -> list[str | HtmlElement]:
        ret: list[str | HtmlElement] = [src.text]
        for sub in src:
            ret.append(self._sub_element(sub))
        return ret

    def _element(self, src: Element) -> HtmlElement:
        if src.html is None:
            raise NotImplementedError
        ret = E(src.html.tag, **src.html.attrib)
        if isinstance(src, MarkupElement):
            self.markup_content(src.content, ret)
        else:
            self.data_content(src, ret, 0)
        return ret

    def _sub_element(self, src: Element) -> HtmlElement:
        ret = self._element(src)
        ret.tail = src.tail
        return ret

    def _proto_section_content(self, src: ProtoSection) -> list[str | HtmlElement]:
        ret: list[str | HtmlElement] = []
        for p in src.presection:
            ret.append(self._element(p))
            ret.append("\n")
        return ret

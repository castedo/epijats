from __future__ import annotations

from typing import TYPE_CHECKING

from lxml.html import HtmlElement, tostring
from lxml.html.builder import E

from .baseprint import ProtoSection
from .tree import Element, DataSubElement, ElementContent, SubElement
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

    def content_to_str(self, src: ElementContent) -> str:
        return _html_to_str(*self._content(src))

    def proto_section_to_str(self, src: ProtoSection) -> str:
        return _html_to_str(*self._proto_section_content(src))

    def _content(self, src: ElementContent) -> list[str | HtmlElement]:
        ret: list[str | HtmlElement] = [src.text]
        for sub in src:
            ret.append(self._sub_element(sub))
        return ret

    def _sub_element(self, src: SubElement | DataSubElement) -> HtmlElement:
        if src.html is None:
            raise NotImplementedError
        if src.data_model:
            ret = E(src.html.tag, **src.html.attrib)
            ret.text = "\n"
            if isinstance(src, DataSubElement):
                self.data_content(src, ret, 0)
            else:
                for it in src.content:
                    sub = self._sub_element(it)
                    sub.tail = "\n"
                    ret.append(sub)
        else:
            ret = E(src.html.tag, *self._content(src.content), **src.html.attrib)
        ret.tail = src.tail
        return ret

    def _proto_section_content(self, src: ProtoSection) -> list[str | HtmlElement]:
        ret: list[str | HtmlElement] = []
        for p in src.presection:
            if ret:
                ret.append("\n")
            ret.append(self._sub_element(p))
        return ret

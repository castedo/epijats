from __future__ import annotations

from lxml.html import HtmlElement, tostring
from lxml.html.builder import E

from .baseprint import Abstract, ProtoSection
from .tree import ElementContent, SubElement


def _html_to_str(*ins: str | HtmlElement) -> str:
    ss = [x if isinstance(x, str) else tostring(x).decode() for x in ins]
    return "".join(ss)


class HtmlGenerator:
    def content_to_str(self, src: ElementContent) -> str:
        return _html_to_str(*self.content(src))

    def proto_section_to_str(self, src: ProtoSection) -> str:
        return _html_to_str(*self._proto_section_content(src))

    def content(self, src: ElementContent) -> list[str | HtmlElement]:
        ret: list[str | HtmlElement] = [src.text]
        for sub in src:
            ret.append(self.sub_element(sub))
        return ret

    def sub_element(self, src: SubElement) -> HtmlElement:
        if src.data_model:
            ret = E(src.html_tag, **src.html_attrib)
            ret.text = "\n"
            for it in src:
                sub = self.sub_element(it)
                sub.tail = "\n"
                ret.append(sub)
        else:
            ret = E(src.html_tag, *self.content(src), **src.html_attrib)
        ret.tail = src.tail
        return ret

    def abstract(self, src: Abstract) -> list[str | HtmlElement]:
        return self._proto_section_content(src)

    def _proto_section_content(self, src: ProtoSection) -> list[str | HtmlElement]:
        ret: list[str | HtmlElement] = []
        for p in src.presection:
            if ret:
                ret.append("\n")
            ret.append(self.sub_element(p))
        return ret

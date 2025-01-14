from __future__ import annotations

from lxml.html import HtmlElement, tostring

from .baseprint import ElementContent, SubElement


def html_to_str(*ins: str | HtmlElement) -> str:
    ss = [x if isinstance(x, str) else tostring(x).decode() for x in ins]
    return "".join(ss)


class HtmlGenerator:

    def content(self, src: ElementContent) -> list[str | HtmlElement]:
        ret: list[str | HtmlElement] = [src.text]
        for sub in src:
            ret += self.content(sub)
            ret.append(sub.tail)
        return ret

    def sub_element(self, src: SubElement) -> HtmlElement:
        return HtmlElement(*self.content(src), src.tail)

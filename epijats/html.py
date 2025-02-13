from __future__ import annotations

from warnings import warn

from lxml.html import HtmlElement, tostring
from lxml.html.builder import E

from . import baseprint as bp
from .tree import Element, MixedContent
from .xml import ElementFormatter


def _html_to_str(*ins: str | HtmlElement) -> str:
    ss = [x if isinstance(x, str) else tostring(x, encoding='unicode') for x in ins]
    return "".join(ss)


class HtmlGenerator(ElementFormatter):
    def start_element(self, src: Element) -> HtmlElement:
        if isinstance(src, bp.TableCell):
            return self.table_cell(src)
        if src.xml.tag == 'table-wrap':
            return E('div', {'class': "table-wrap"})
        if src.html is None:
            warn(f"Unknown XML {src.xml.tag}")
            return E('div', {'class': f"unknown-xml xml-{src.xml.tag}"})
        return E(src.html.tag, **src.html.attrib)

    def table_cell(self, src: bp.TableCell) -> HtmlElement:
        attrib = {}
        align = src.xml.attrib.get('align')
        if align:
            attrib['style'] = f"text-align: {align};"
        return E(src.xml.tag, attrib)

    def content_to_str(self, src: MixedContent) -> str:
        ss: list[str | HtmlElement] = [src.text]
        for sub in src:
            ss.append(self.tailed_html_element(sub))
        return _html_to_str(*ss)

    def proto_section_to_str(self, src: bp.ProtoSection) -> str:
        return _html_to_str(*self._proto_section_content(src))

    def html_element(self, src: Element) -> HtmlElement:
        ret = self.start_element(src)
        self.copy_content(src, ret, 0)
        return ret

    def tailed_html_element(self, src: Element) -> HtmlElement:
        ret = self.html_element(src)
        ret.tail = src.tail
        return ret

    def _proto_section_content(
        self,
        src: bp.ProtoSection,
        title: MixedContent | None = None,
        xid: str | None = None,
        level: int = 0,
    ) -> list[str | HtmlElement]:
        if level < 6:
            level += 1
        ret: list[str | HtmlElement] = []
        if title:
            h = E(f"h{level}", title.text)
            if xid is not None:
                h.attrib['id'] = xid
            for s in title:
                h.append(self.tailed_html_element(s))
            h.tail = "\n"
            ret.append(h)
        for p in src.presection:
            ret.append(self.html_element(p))
            ret.append("\n")
        for ss in src.subsections:
            ret.extend(self._proto_section_content(ss, ss.title, ss.id, level))
        return ret

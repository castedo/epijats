from __future__ import annotations

from typing import Iterable
from warnings import warn

from lxml.html import HtmlElement, tostring
from lxml.html.builder import E

from . import baseprint as bp
from .biblio import CiteprocBiblioFormatter
from .tree import Element, MixedContent
from .xml import ElementFormatter


def html_content_to_str(ins: Iterable[str | HtmlElement]) -> str:
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
        return html_content_to_str(ss)

    def proto_section_to_str(self, src: bp.ProtoSection) -> str:
        return html_content_to_str(self._proto_section_content(src))

    def html_element(self, src: Element) -> HtmlElement:
        ret = self.start_element(src)
        self.copy_content(src, ret, 0)
        return ret

    def tailed_html_element(self, src: Element) -> HtmlElement:
        ret = self.html_element(src)
        ret.tail = src.tail
        return ret

    def _copy_content(self, src: MixedContent, dest: HtmlElement) -> None:
        dest.text = src.text
        for s in src:
            dest.append(self.tailed_html_element(s))

    def _proto_section_content(
        self,
        src: bp.ProtoSection,
        title: MixedContent | None = None,
        xid: str | None = None,
        level: int = 0,
    ) -> Iterable[str | HtmlElement]:
        if level < 6:
            level += 1
        ret: list[str | HtmlElement] = []
        if title:
            h = E(f"h{level}")
            if xid is not None:
                h.attrib['id'] = xid
            self._copy_content(title, h)
            h.tail = "\n"
            ret.append(h)
        for p in src.presection:
            ret.append(self.html_element(p))
            ret.append("\n")
        for ss in src.subsections:
            ret.extend(self._proto_section_content(ss, ss.title, ss.id, level))
        return ret

    def _references(self, src: bp.BiblioRefList) -> Iterable[str | HtmlElement]:
        ret: list[str | HtmlElement] = []
        if src.title:
            h = E('h2')
            self._copy_content(src.title, h)
            h.tail = '\n'
            ret.append(h)
        formatter = CiteprocBiblioFormatter()
        ol = formatter.to_element(src.references)
        ol.tail = "\n"
        ret.append(ol)
        return ret

    def html_body_content(self, src: bp.Baseprint) -> str:
        frags = list(self._proto_section_content(src.body))
        if src.ref_list:
            frags += self._references(src.ref_list)
        return html_content_to_str(frags)

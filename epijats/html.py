from __future__ import annotations

from typing import Iterable
from warnings import warn

from lxml.html import HtmlElement, tostring
from lxml.html.builder import E

from . import baseprint as bp
from .biblio import CiteprocBiblioFormatter
from .tree import CitationTuple, Element, MixedContent
from .xml import (
    CommonContentFormatter, ElementFormatter, MarkupContentFormatter
)


def html_content_to_str(ins: Iterable[str | HtmlElement]) -> str:
    ss = [x if isinstance(x, str) else tostring(x, encoding='unicode') for x in ins]
    return "".join(ss)


class HtmlFormatter(ElementFormatter):
    def __init__(self) -> None:
        self.table_cell = TableCellHtmlizer(self)
        self.citation_tuple = CitationTupleHtmlizer(self)
        self.common = CommonContentFormatter(self)

    def __call__(self, src: Element, level: int) -> HtmlElement:
        if isinstance(src, bp.TableCell):
            return self.table_cell.htmlize(src, level)
        if isinstance(src, CitationTuple):
            return self.citation_tuple.htmlize(src, level)
        if src.xml.tag == 'table-wrap':
            ret = E('div', {'class': "table-wrap"})
        elif src.html is None:
            warn(f"Unknown XML {src.xml.tag}")
            ret = E('div', {'class': f"unknown-xml xml-{src.xml.tag}"})
        else:
            ret = E(src.html.tag, src.html.attrib)
        self.common.format_content(src, ret, level)
        return ret


class TableCellHtmlizer:
    def __init__(self, sub: ElementFormatter):
        self.markup = MarkupContentFormatter(sub)

    def htmlize(self, src: bp.TableCell, level: int) -> HtmlElement:
        attrib = {}
        align = src.xml.attrib.get('align')
        if align:
            attrib['style'] = f"text-align: {align};"
        ret = E(src.xml.tag, attrib)
        self.markup.format_content(src, ret, level)
        return ret


class CitationTupleHtmlizer:
    def __init__(self, form: HtmlFormatter):
        self.form = form

    def htmlize(self, src: CitationTuple, level: int) -> HtmlElement:
        assert src.xml.tag == 'sup'
        ret = E('span', {'class': "citation-tuple"})
        ret.text = " ["
        sub: HtmlElement | None = None
        for it in src:
            sub = self.form(it, level + 1)
            sub.tail = ","
            ret.append(sub)
        if sub is None:
            warn("Citation tuple is empty")
            ret.text += "]"
        else:
            sub.tail = "]"
        return ret


class HtmlGenerator:
    def __init__(self) -> None:
        self._html = HtmlFormatter()

    def tailed_html_element(self, src: Element) -> HtmlElement:
        ret = self._html(src, 0)
        ret.tail = src.tail
        return ret

    def content_to_str(self, src: MixedContent) -> str:
        ss: list[str | HtmlElement] = [src.text]
        for sub in src:
            ss.append(self.tailed_html_element(sub))
        return html_content_to_str(ss)

    def proto_section_to_str(self, src: bp.ProtoSection) -> str:
        return html_content_to_str(self._proto_section_content(src))

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
            ret.append(self._html(p, 0))
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

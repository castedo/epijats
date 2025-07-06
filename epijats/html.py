from __future__ import annotations

from typing import TYPE_CHECKING, Iterable
from warnings import warn

from lxml import etree as ET
from lxml.etree import Element as E

from . import baseprint as bp
from .biblio import CiteprocBiblioFormatter
from .parse.math import MathmlElement
from .tree import Citation, CitationTuple, MixedContent, PureElement
from .xml import CommonContentFormatter, ElementFormatter, MarkupFormatter

if TYPE_CHECKING:
    from .xml import XmlElement


def html_content_to_str(ins: Iterable[str | XmlElement]) -> str:
    ss = []
    for x in ins:
        if isinstance(x, str):
            ss.append(x)
        else:
            ss.append(ET.tostring(x, encoding='unicode', method='html'))
    return "".join(ss)


HTML_FROM_XML = {
  'bold': 'strong',
  'break': 'br',
  'code': 'pre',
  'def': 'dd',
  'def-list': 'dl',
  'disp-quote': 'blockquote',
  'italic': 'em',
  'list-item': 'li',
  'monospace': 'samp',
  'p': 'p',
  'preformat': 'pre',
  'sub': 'sub',
  'sup': 'sup',
  'tbody': 'tbody',
  'term': 'dt',
  'thead': 'thead',
  'tr': 'tr',
}


class HtmlFormatter(ElementFormatter):
    def __init__(self) -> None:
        self.citation_tuple = CitationTupleHtmlizer(self)
        self.common = CommonContentFormatter(self)

    def to_one_only(self, src: PureElement, level: int) -> XmlElement:
        if isinstance(src, CitationTuple):
            return self.citation_tuple.htmlize(src, level)
        html_tag = HTML_FROM_XML.get(src.xml.tag)
        if html_tag:
            ret = E(html_tag)
        elif isinstance(src, Citation):
            ret = E('a', {'href': '#' + src.rid})
        elif isinstance(src, bp.CrossReference):
            ret = E('a', {'href': '#' + src.rid})
        elif isinstance(src, bp.Hyperlink):
            ret = E('a', {'href': src.href})
        elif isinstance(src, bp.List):
            ret = E('ol' if src.list_type == bp.ListTypeCode.ORDER else 'ul')
        elif src.xml.tag == 'table-wrap':
            ret = E('div', {'class': "table-wrap"})
        elif src.xml.tag == 'table':
            ret = self.table(src, level)
        elif src.xml.tag in ('col', 'colgroup'):
            ret = E(src.xml.tag, dict(sorted(src.xml.attrib.items())))
        elif src.xml.tag in ('th', 'td'):
            ret = self.table_cell(src, level)
        elif isinstance(src, MathmlElement):
            ret = E(src.html.tag, src.html.attrib)
        else:
            warn(f"Unknown XML {src.xml.tag}")
            ret = E('div', {'class': f"unknown-xml xml-{src.xml.tag}"})
        self.common.format_content(src, level, ret)
        return ret

    def root(self, src: PureElement) -> XmlElement:
        return self.to_one_only(src, 0)

    def format(self, src: PureElement, level: int) -> Iterable[XmlElement]:
        ret: list[XmlElement]
        if src.xml.tag == 'def-item':
            ret = []
            for it in src:
                ret.extend(self.format(it, level))
        else:
            ret = [self.to_one_only(src, level)]
        return ret

    def table(self, src: PureElement, level: int) -> XmlElement:
        attrib = src.xml.attrib.copy()
        attrib.setdefault('frame', 'hsides')
        attrib.setdefault('rules', 'groups')
        return E(src.xml.tag, dict(sorted(attrib.items())))

    def table_cell(self, src: PureElement, level: int) -> XmlElement:
        attrib = {}
        for key, value in src.xml.attrib.items():
            if key in {'rowspan', 'colspan'}:
                attrib[key] = value
            elif key == 'align':
                    attrib['style'] = f"text-align: {value};"
            else:
                warn(f"Unknown table cell attribute {key}")
        return E(src.xml.tag, dict(sorted(attrib.items())))


class CitationTupleHtmlizer:
    def __init__(self, html: HtmlFormatter):
        self._html = html

    def htmlize(self, src: CitationTuple, level: int) -> XmlElement:
        assert src.xml.tag == 'sup'
        ret = E('span', {'class': "citation-tuple"})
        ret.text = " ["
        sub: XmlElement | None = None
        for it in src:
            for sub in self._html.format(it, level + 1):
                sub.tail = ","
                ret.append(sub)
        if sub is None:
            warn("Citation is missing")
            ret.text += "citation missing]"
        else:
            sub.tail = "]"
        return ret


class HtmlGenerator:
    def __init__(self) -> None:
        self._html = HtmlFormatter()
        self._markup = MarkupFormatter(self._html)

    def content_to_str(self, src: MixedContent) -> str:
        ss: list[str | XmlElement] = [src.text]
        for it in src:
            for sub in self._html.format(it, 0):
                ss.append(sub)
            ss.append(it.tail)
        return html_content_to_str(ss)

    def proto_section_to_str(self, src: bp.ProtoSection) -> str:
        return html_content_to_str(self._proto_section_content(src))

    def _proto_section_content(
        self,
        src: bp.ProtoSection,
        title: MixedContent | None = None,
        xid: str | None = None,
        level: int = 0,
    ) -> Iterable[str | XmlElement]:
        if level < 6:
            level += 1
        ret: list[str | XmlElement] = []
        if title:
            h = E(f"h{level}")
            if xid is not None:
                h.attrib['id'] = xid
            self._markup.format(title, level, h)
            h.tail = "\n"
            ret.append(h)
        for p in src.presection:
            for sub in self._html.format(p, 0):
                ret.append(sub)
                ret.append("\n")
        for ss in src.subsections:
            ret.extend(self._proto_section_content(ss, ss.title, ss.id, level))
        return ret

    def html_references(
        self, src: bp.BiblioRefList, abridged: bool = False,
    ) -> str:
        frags: list[str | XmlElement] = []
        if src.title:
            h = E('h2')
            self._markup.format(src.title, 0, h)
            h.tail = '\n'
            frags.append(h)
        formatter = CiteprocBiblioFormatter(abridged)
        ol = formatter.to_element(src.references)
        ol.tail = "\n"
        frags.append(ol)
        return html_content_to_str(frags)

    def html_body_content(self, src: bp.Baseprint) -> str:
        frags = list(self._proto_section_content(src.body))
        return html_content_to_str(frags)

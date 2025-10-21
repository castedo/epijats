from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Iterable, Iterator
from warnings import warn

from .. import dom
from ..biblio import CiteprocBiblioFormatter
from ..document import Abstract
from ..math import FormulaElement
from ..parse.baseprint import get_ET
from ..elements import Citation, CitationTuple
from ..tree import MixedContent, PureElement
from .format import CommonContentFormatter, ElementFormatter, MarkupFormatter

if TYPE_CHECKING:
    from ..typeshed import XmlElement


ET = get_ET(use_lxml=False)


class Htmlizer(ABC):
    @abstractmethod
    def handle(self, src: PureElement, level: int, dest: list[XmlElement]) -> bool: ...


class BaseHtmlizer(Htmlizer, ElementFormatter):
    def __init__(self, subformat: ElementFormatter):
        self.common = CommonContentFormatter(subformat)

    def format(self, src: PureElement, level: int) -> Iterable[XmlElement]:
        ret: list[XmlElement] = []
        if not self.handle(src, level, ret):
            warn(f"Unknown XML {src.xml.tag}")
            xe = ET.Element('span', {'class': f"unknown-xml xml-{src.xml.tag}"})
            self.common.format_content(src, level, xe)
            ret = [xe]
        return ret


class UnionHtmlizer(BaseHtmlizer):
    def __init__(self, subs: Iterable[Htmlizer] = ()) -> None:
        super().__init__(self)
        self._subs = list(subs)

    def __ior__(self, other: Htmlizer) -> UnionHtmlizer:
        self._subs.append(other)
        return self

    def handle(self, src: PureElement, level: int, dest: list[XmlElement]) -> bool:
        return any(s.handle(src, level, dest) for s in self._subs)


HTML_FROM_XML = {
    'b': 'strong',
    'br': 'br',
    'code': 'code',
    'dd': 'dd',
    'blockquote': 'blockquote',
    'div': 'div',
    'dl': 'dl',
    'dt': 'dt',
    'format-issue': 'output',
    'i': 'em',
    'li': 'li',
    'tt': 'samp',
    'ol': 'ol',
    'p': 'p',
    'pre': 'pre',
    'sub': 'sub',
    'sup': 'sup',
    'tbody': 'tbody',
    'thead': 'thead',
    'tr': 'tr',
    'ul': 'ul',
}


class DefaultHtmlizer(BaseHtmlizer):
    def __init__(self, html: ElementFormatter):
        super().__init__(html)

    def handle(self, src: PureElement, level: int, dest: list[XmlElement]) -> bool:
        E = ET.Element
        html_tag = HTML_FROM_XML.get(src.xml.tag)
        ret: XmlElement
        if html_tag:
            ret = E(html_tag)
        elif isinstance(src, Citation):
            ret = E('a', {'href': '#' + src.rid})
        elif isinstance(src, dom.CrossReference):
            ret = E('a', {'href': '#' + src.rid})
        elif isinstance(src, dom.ExternalHyperlink):
            ret = E('a', {'href': src.href, 'rel': 'external'})
        else:
            return False
        self.common.format_content(src, level, ret)
        dest.append(ret)
        return True


class TableHtmlizer(BaseHtmlizer):
    def __init__(self, html: ElementFormatter):
        super().__init__(html)

    def handle(self, src: PureElement, level: int, dest: list[XmlElement]) -> bool:
        ret: XmlElement
        if src.xml.tag == 'table-wrap':
            ret = ET.Element('div', {'class': "table-wrap"})
        elif src.xml.tag == 'table':
            ret = self.table(src, level)
        elif src.xml.tag in ('col', 'colgroup'):
            ret = ET.Element(src.xml.tag, dict(sorted(src.xml.attrib.items())))
        elif src.xml.tag in ('th', 'td'):
            ret = self.table_cell(src, level)
        else:
            return False
        self.common.format_content(src, level, ret)
        dest.append(ret)
        return True

    def table(self, src: PureElement, level: int) -> XmlElement:
        attrib = src.xml.attrib.copy()
        attrib.setdefault('frame', 'hsides')
        attrib.setdefault('rules', 'groups')
        return ET.Element(src.xml.tag, dict(sorted(attrib.items())))  # type: ignore[no-any-return]

    def table_cell(self, src: PureElement, level: int) -> XmlElement:
        attrib = {}
        for key, value in src.xml.attrib.items():
            if key in {'rowspan', 'colspan'}:
                attrib[key] = value
            elif key == 'align':
                attrib['style'] = f"text-align: {value};"
            else:
                warn(f"Unknown table cell attribute {key}")
        return ET.Element(src.xml.tag, dict(sorted(attrib.items())))  # type: ignore[no-any-return]


class CitationTupleHtmlizer(Htmlizer):
    def __init__(self, html: ElementFormatter):
        self._html = html

    def handle(self, src: PureElement, level: int, dest: list[XmlElement]) -> bool:
        if not isinstance(src, CitationTuple):
            return False
        assert src.xml.tag == 'sup'
        ret = ET.Element('span', {'class': "citation-tuple"})
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
        dest.append(ret)
        return True


class MathHtmlizer(Htmlizer):
    def __init__(self) -> None:
        self.bare_tex = False

    def handle(self, src: PureElement, level: int, dest: list[XmlElement]) -> bool:
        if isinstance(src, FormulaElement):
            ret = ET.Element('span', {'class': f"math {src.formula_style}"})
            ret.text = src.tex
            self.bare_tex = True
        else:
            return False
        dest.append(ret)
        return True


class HtmlGenerator:
    def __init__(self) -> None:
        self._math = MathHtmlizer()
        self._html = UnionHtmlizer()
        self._html |= self._math
        self._html |= TableHtmlizer(self._html)
        self._html |= CitationTupleHtmlizer(self._html)
        self._html |= TableHtmlizer(self._html)
        self._html |= DefaultHtmlizer(self._html)
        self._markup = MarkupFormatter(self._html)

    @property
    def bare_tex(self) -> bool:
        return self._math.bare_tex

    def _html_content_to_str(self, ins: Iterable[str | XmlElement]) -> str:
        ss = []
        for x in ins:
            if isinstance(x, str):
                ss.append(x)
            else:
                ss.append(ET.tostring(x, encoding='unicode', method='html'))
        return "".join(ss)

    def content_to_str(self, src: MixedContent) -> str:
        ss: list[str | XmlElement] = [src.text]
        for it in src:
            for sub in self._html.format(it, 0):
                ss.append(sub)
            if it.tail:
                ss.append(it.tail)
        return self._html_content_to_str(ss)

    def abstract_to_str(self, src: Abstract) -> str:
        return self._html_content_to_str(self._blocks_content(src.blocks))

    def proto_section_to_str(self, src: dom.ProtoSection) -> str:
        return self._html_content_to_str(self._proto_section_content(src))

    def _blocks_content(self, src: Iterable[PureElement]) -> Iterator[XmlElement]:
        for p in src:
            for sub in self._html.format(p, 0):
                sub.tail = "\n"
                yield sub

    def _proto_section_content(
        self,
        src: dom.ProtoSection,
        title: MixedContent | None = None,
        xid: str | None = None,
        level: int = 0,
    ) -> Iterator[XmlElement]:
        if level < 6:
            level += 1
        if title:
            h = ET.Element(f"h{level}")
            if xid is not None:
                h.attrib['id'] = xid
            self._markup.format(title, level, h)
            h.tail = "\n"
            yield h
        yield from self._blocks_content(src.presection)
        for ss in src.subsections:
            section = ET.Element("section")
            section.text = "\n"
            section.extend(self._proto_section_content(ss, ss.title, ss.id, level))
            section.tail = "\n"
            yield section

    def html_references(self, src: dom.BiblioRefList, *, abridged: bool = False) -> str:
        frags: list[str | XmlElement] = []
        h = ET.Element('h2')
        h.text = "References"
        h.tail = '\n'
        frags.append(h)
        formatter = CiteprocBiblioFormatter(abridged=abridged)
        ol = formatter.to_element(src.references)
        ol.tail = "\n"
        frags.append(ol)
        return self._html_content_to_str(frags)

    def html_body_content(self, src: dom.Article) -> str:
        frags = list(self._proto_section_content(src.body))
        return self._html_content_to_str(frags)

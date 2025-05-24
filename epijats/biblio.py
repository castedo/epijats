from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from importlib import resources
from html import escape
from typing import TYPE_CHECKING, cast

import citeproc
from lxml import html
from lxml.html import HtmlElement

from . import baseprint as bp

if TYPE_CHECKING:
    from .typeshed import JSONType


JATS_TO_CSL_VAR = {
    'comment': 'note',
    'edition': 'edition',
    'isbn': 'ISBN',
    'issn': 'ISSN',
    'issue': 'issue',
    'publisher-loc': 'publisher-place',
    'publisher-name': 'publisher',
    'title': 'title',
    'uri': 'URL',
    'volume': 'volume',
}

JATS_TO_CSL_TYPE = {
    'book': 'book',
    'journal': 'article-journal',
}


def hyperlink(html_content: str, prepend: str | None = None) -> str:
    frags = html.fragments_fromstring(html_content)
    if not frags or not isinstance(frags[0], str):
        return html_content
    url = frags[0]
    if prepend:
        url = prepend + url
    element = html.builder.A(url, href=url)
    return html.tostring(element, encoding='unicode')


def date_parts(src: bp.Date) -> JSONType:
    parts: list[JSONType] = [src.year]
    if src.month:
        parts.append(src.month)
        if src.day:
            parts.append(src.day)
    return {'date-parts': [parts]}


class CsljsonItem(dict[str, 'JSONType']):
    def __init__(self) -> None:
        self['type'] = ''

    def set_str(self, key: str, src: str | int | None) -> None:
        if src is not None:
            if isinstance(src, int):
                src = str(src)
            self[key] = escape(src, quote=False)

    def hyperlinkize(self) -> CsljsonItem:
        for key, value in self.items():
            match key:
                case 'URL':
                    self[key] = hyperlink(cast(str, value))
                case 'DOI':
                    self[key] = hyperlink(cast(str, value), "https://doi.org/")
        return self

    def append_author(self, src: bp.PersonName | str) -> None:
        authors = cast(list['JSONType'], self.setdefault('author', []))
        a: dict[str, JSONType] = {}
        if isinstance(src, bp.PersonName):
            if src.surname:
                a['family'] = escape(src.surname, quote=False)
            if src.given_names:
                a['given'] = escape(src.given_names, quote=False)
        else:
            assert isinstance(src, str)
            a['literal'] = escape(str(src), quote=False)
        authors.append(a)

    def assign_csjson_titles(self, src: bp.BiblioRefItem) -> None:
        if src.article_title:
            self.set_str('container-title', src.source)
            self.set_str('title', src.article_title)
        else:
            self.set_str('title', src.source)

    @staticmethod
    def from_ref_item(src: bp.BiblioRefItem) -> CsljsonItem:
        ret = CsljsonItem()
        ret.set_str('id', src.id)
        for jats_key, value in src.biblio_fields.items():
            if csl_key := JATS_TO_CSL_VAR.get(jats_key):
                ret.set_str(csl_key, value)
        ret.assign_csjson_titles(src)
        if src.date:
            ret['issued'] = date_parts(src.date)
        if src.access_date:
            ret['accessed'] = date_parts(src.access_date)
        for person in src.authors:
            ret.append_author(person)
        ret.set_str('edition', src.edition)
        if fpage := src.biblio_fields.get('fpage'):
            page = fpage
            if lpage := src.biblio_fields.get('lpage'):
                page += f"-{lpage}"
            ret.set_str('page', page)
        for pub_id_type, value in src.pub_ids.items():
            ret.set_str(pub_id_type.upper(), value)
        return ret


class BiblioFormatter(ABC):
    @abstractmethod
    def to_element(self, refs: Sequence[bp.BiblioRefItem]) -> HtmlElement: ...

    def to_str(self, refs: Sequence[bp.BiblioRefItem]) -> str:
        e = self.to_element(refs)
        e.tail = "\n"
        return html.tostring(e, encoding='unicode')


def put_tags_on_own_lines(e: HtmlElement) -> None:
    e.text = "\n{}".format(e.text or '')
    s = None
    for s in e:
        pass
    if s is None:
        e.text += "\n"
    else:
        s.tail = "{}\n".format(s.tail or '')


def divs_from_citeproc_bibliography(
    biblio: citeproc.CitationStylesBibliography
) -> list[HtmlElement]:
    ret = []
    for item in biblio.bibliography():
        s = str(item).replace("..\n", ".\n").strip()
        frags = html.fragments_fromstring(s)
        div = html.builder.DIV(*frags)
        put_tags_on_own_lines(div)
        div.tail = "\n"
        ret.append(div)
    return ret


class CiteprocBiblioFormatter(BiblioFormatter):
    def __init__(self, abridged: bool = False):
        self._abridged = abridged
        filename = "abridged.csl" if abridged else "full-preview.csl"
        r = resources.files(__package__) / f"csl/{filename}"
        with resources.as_file(r) as csl_file:
            self._style = citeproc.CitationStylesStyle(csl_file, validate=False)

    def to_element(self, refs: Sequence[bp.BiblioRefItem]) -> HtmlElement:
        csljson = [CsljsonItem.from_ref_item(r).hyperlinkize() for r in refs]
        bib_source = citeproc.source.json.CiteProcJSON(csljson)
        biblio = citeproc.CitationStylesBibliography(
            self._style, bib_source, citeproc.formatter.html
        )
        for ref_item in refs:
            c = citeproc.Citation([citeproc.CitationItem(ref_item.id)])
            biblio.register(c)
        divs = divs_from_citeproc_bibliography(biblio)
        assert len(divs) == len(refs)
        ret = html.builder.OL()
        ret.text = "\n"
        for i in range(len(divs)):
            li = html.builder.LI()
            li.attrib['id'] = refs[i].id
            li.text = "\n"
            li.append(divs[i])
            if not self._abridged:
                if comment := refs[i].biblio_fields.get('comment'):
                    div2 = html.builder.DIV(comment)
                    div2.tail = "\n"
                    li.append(div2)
            li.tail = "\n"
            ret.append(li)
        return ret

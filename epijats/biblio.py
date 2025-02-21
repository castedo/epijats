from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from collections.abc import Iterable
from importlib import resources
from html import escape
from typing import TypeAlias, cast

import citeproc
from lxml import html
from lxml.html import HtmlElement

from . import baseprint as bp


JSONType: TypeAlias = (
    None | str | int | float | list['JSONType'] | dict[str, 'JSONType']
)

JATS_TO_CSL_VAR = {
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


class CsljsonItem(dict[str, JSONType]):
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
        authors = cast(list[JSONType], self.setdefault('author', []))
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
        match src.publication_type:
            case 'book':
                self.set_str('title', src.source)
            case _:
                self.set_str('container-title', src.source)
                self.set_str('title', src.article_title)

    def assign_dates(self, src: bp.BiblioRefItem) -> None:
        if src.year:
            parts: list[JSONType] = [src.year]
            if src.month:
                parts.append(src.month)
            self['issued'] = {'date-parts': [parts]}

    @staticmethod
    def from_ref_item(src: bp.BiblioRefItem) -> CsljsonItem:
        ret = CsljsonItem()
        ret.set_str('id', src.id)
        ret['type'] = JATS_TO_CSL_TYPE.get(src.publication_type, '')
        for jats_key, value in src.biblio_fields.items():
            if csl_key := JATS_TO_CSL_VAR.get(jats_key):
                ret.set_str(csl_key, value)
        ret.assign_csjson_titles(src)
        ret.assign_dates(src)
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
    def to_element(self, refs: Iterable[bp.BiblioRefItem]) -> HtmlElement: ...

    def to_str(self, refs: Iterable[bp.BiblioRefItem]) -> str:
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


class CiteprocBiblioFormatter(BiblioFormatter):
    def __init__(self, csl: Path | None = None):
        if csl is None:
            r = resources.files(__package__) / "csl/full-preview.csl"
            with resources.as_file(r) as csl_file:
                self._style = citeproc.CitationStylesStyle(csl_file, validate=False)
        else:
            self._style = citeproc.CitationStylesStyle(Path(csl))

    def to_element(self, refs: Iterable[bp.BiblioRefItem]) -> HtmlElement:
        csljson = [CsljsonItem.from_ref_item(r).hyperlinkize() for r in refs]
        bib_source = citeproc.source.json.CiteProcJSON(csljson)
        biblio = citeproc.CitationStylesBibliography(
            self._style, bib_source, citeproc.formatter.html
        )
        case_sensitive_ids = []
        for ref_item in refs:
            case_sensitive_ids.append(ref_item.id)
            c = citeproc.Citation([citeproc.CitationItem(ref_item.id)])
            biblio.register(c)
        strs = [str(s) for s in biblio.bibliography()]
        assert len(strs) == len(case_sensitive_ids)
        ret = html.builder.OL()
        ret.text = "\n"
        for i in range(len(strs)):
            s = strs[i].replace("..\n", ".\n")
            frags = html.fragments_fromstring(s)
            li = html.builder.LI(*frags)
            li.attrib['id'] = case_sensitive_ids[i]
            put_tags_on_own_lines(li)
            li.tail = "\n"
            ret.append(li)
        return ret

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from collections.abc import Iterable, Sequence
from importlib import resources
from html import escape
from typing import Any, TypeAlias

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


class CsljsonItem(dict[str, Any]): #JSONType]):
    def set_str(self, key: str, src: str | int | None) -> None:
        if src is not None:
            if isinstance(src, int):
                src = str(src)
            self[key] = escape(src, quote=False)

    def append_author(self, src: bp.PersonName | str) -> None:
        authors = self.setdefault('author', [])
        if isinstance(src, bp.PersonName):
            a: dict[str, JSONType] = {}
            if src.surname:
                a['family'] = escape(src.surname)
            if src.given_names:
                a['given'] = escape(src.given_names)
            authors.append(a)
        else:
            raise NotImplementedError

    def assign_csjson_titles(self, src: bp.BiblioRefItem) -> None:
        match src.publication_type:
            case 'book':
                self.set_str('title', src.source)
            case _:
                self.set_str('container-title', src.source)
                self.set_str('title', src.article_title)

    def assign_dates(self, src: bp.BiblioRefItem) -> None:
        if src.year:
            parts = [src.year]
            if src.month:
                parts.append(src.month)
            self['issued'] = {'date-parts': [parts]}

    @staticmethod
    def from_ref_item(src: bp.BiblioRefItem) -> JSONType:
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
    def to_elements(
        self, refs: Iterable[bp.BiblioRefItem]
    ) -> Sequence[HtmlElement]: ...

    def to_str(self, refs: Iterable[bp.BiblioRefItem]) -> str:
        es = self.to_elements(refs)
        lines = [html.tostring(e, encoding='unicode') for e in es]
        return "\n".join([*lines, ''])


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

    def to_elements(self, refs: Iterable[bp.BiblioRefItem]) -> Sequence[HtmlElement]:
        ret = []
        csljson = [CsljsonItem.from_ref_item(r) for r in refs]
        bib_source = citeproc.source.json.CiteProcJSON(csljson)
        biblio = citeproc.CitationStylesBibliography(
            self._style, bib_source, citeproc.formatter.html
        )
        for ref_item in refs:
            c = citeproc.Citation([citeproc.CitationItem(ref_item.id)])
            biblio.register(c)
        for item in biblio.bibliography():
            s = str(item)
            s = s.replace("..\n", ".\n")
            frags = html.fragments_fromstring(s)
            li = html.builder.LI(*frags)
            put_tags_on_own_lines(li)
            li.tail = "\n"
            ol = html.builder.OL(li)
            ol.text = "\n"
            ret.append(ol)
        return ret

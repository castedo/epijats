from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from collections.abc import Iterable, Sequence
from typing import Any, TypeAlias

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


def csljson_from_authors(src: list[bp.PersonName | str]) -> JSONType:
    authors: list[JSONType] = []
    for name in src:
        if isinstance(name, bp.PersonName):
            a: dict[str, JSONType] = {}
            if name.surname:
                a['family'] = name.surname
            if name.given_names:
                a['given'] = name.given_names
        else:
            raise NotImplementedError
        authors.append(a)
    return authors


def assign_csjson_titles(src: bp.BiblioRefItem, dest: dict[str, Any]) -> None:
    match src.publication_type:
        case 'book':
            if src.source is not None:
                dest['title'] = src.source
        case _:
            if src.source is not None:
                dest['container-title'] = src.source
            if src.article_title is not None:
                dest['title'] = src.article_title


def csljson_from_ref_item(src: bp.BiblioRefItem) -> JSONType:
    ret: dict[str, Any] = {'id': src.id}
    ret['type'] = JATS_TO_CSL_TYPE.get(src.publication_type, '')
    for jats_key, value in src.biblio_fields.items():
        if csl_key := JATS_TO_CSL_VAR.get(jats_key):
            ret[csl_key] = value
    assign_csjson_titles(src, ret)
    if src.year:
        parts = [src.year]
        if src.month:
            parts.append(src.month)
        ret['issued'] = {'date-parts': [parts]}
    ret['author'] = csljson_from_authors(src.authors)
    if src.edition is not None:
        ret['edition'] = src.edition
    if fpage := src.biblio_fields.get('fpage'):
        ret['page'] = fpage
        if lpage := src.biblio_fields.get('lpage'):
            ret['page'] += f"-{lpage}"
    for pub_id_type, value in src.pub_ids.items():
        ret[pub_id_type.upper()] = value
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
    def __init__(self, csl: Path):
        import citeproc

        self._style = citeproc.CitationStylesStyle(Path(csl))

    def to_elements(self, refs: Iterable[bp.BiblioRefItem]) -> Sequence[HtmlElement]:
        import citeproc

        ret = []
        csljson = [csljson_from_ref_item(r) for r in refs]
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

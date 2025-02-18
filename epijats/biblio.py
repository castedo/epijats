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

JATS_TO_CSL = {
    'edition': 'edition',
    'isbn': 'ISBN',
    'issn': 'ISSN',
    'publisher-loc': 'publisher-place',
    'publisher-name': 'publisher',
    'title': 'title',
    'uri': 'URL',
    'volume': 'volume',
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


def csljson_from_ref_item(src: bp.BiblioRefItem) -> JSONType:
    ret: dict[str, Any] = {
        'id': src.id,
        'type': src.publication_type,
    }
    for jats_key, value in src.biblio_fields.items():
        if csl_key := JATS_TO_CSL.get(jats_key):
            ret[csl_key] = value
    if src.year:
        parts = [src.year]
        if src.month:
            parts.append(src.month)
        ret['issued'] = {'date-parts': [parts]}
    if source := src.biblio_fields.get('source'):
        # TODO: special handling for diff types
        ret['title'] = source
    if src.article_title is not None:
        ret['title'] = src.article_title
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
            frags = html.fragments_fromstring(str(item))
            ret.append(html.builder.DIV(*frags))
        return ret

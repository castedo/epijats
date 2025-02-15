from __future__ import annotations

from typing import Any, Mapping, TypeAlias

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
        # MixedContent source type
        ret['title'] = source
    if src.article_title is not None:
        # TODO: need to do something with hypertext
        ret['title'] = src.article_title.text
    authors: list[Mapping[str, JSONType]] = []
    for name in src.authors:
        if isinstance(name, bp.PersonName):
            a = {}
            if name.surname:
                a['family'] = name.surname
            if name.given_names:
                a['given'] = name.given_names
        else:
            raise NotImplementedError
        authors.append(a)
    ret['author'] = authors
    if fpage := src.biblio_fields.get('fpage'):
        ret['page'] = fpage
        if lpage := src.biblio_fields.get('lpage'):
            ret['page'] += f"-{lpage}"
    for pub_id_type, value in src.pub_ids.items():
        ret[pub_id_type.upper()] = value
    return ret

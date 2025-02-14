from __future__ import annotations

from typing import Any, Mapping, TypeAlias

from . import baseprint as bp


JSONType: TypeAlias = None | str | int | float | list['JSONType'] | dict[str, 'JSONType']


JATS_TO_CSL = {
  'publisher-loc': 'publisher-place',
  'publisher-name': 'publisher',
  'edition': 'edition',
  'isbn': 'ISBN',
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
        ret['issued'] = {'date-parts': [[src.year]]}
    if source := src.biblio_fields.get('source'):
        # TODO: special handling for diff types
        # MixedContent source type
        ret['title'] = source
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
    return ret

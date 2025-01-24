from __future__ import annotations

from . import baseprint
from .tree import DataContent, MarkupContent


def contrib(src: baseprint.Author) -> DataContent:
    ret = DataContent('contrib', {'contrib-type': 'author'})
    if src.orcid:
        url = str(src.orcid)
        ret.append(MarkupContent('contrib-id', {'contrib-id-type': 'orcid'}, url))
    name = DataContent('name')
    if src.surname:
        name.append(MarkupContent('surname', {}, src.surname))
    if src.given_names:
        name.append(MarkupContent('given-names', {}, src.given_names))
    ret.append(name)
    if src.email:
        ret.append(MarkupContent('email', {}, src.email))
    return ret


def contrib_group(src: list[baseprint.Author]) -> DataContent:
    ret = DataContent('contrib-group', {})
    for a in src:
        ret.append(contrib(a))
    return ret

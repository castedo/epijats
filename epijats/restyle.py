from __future__ import annotations

from . import baseprint
from .tree import DataElement, MarkupElement, MixedContent, StartTag


def title_group(src: MixedContent) -> DataElement:
    title = MarkupElement('article-title', src.text)
    for it in src:
        title.content.append(it)
    return DataElement('title-group', [title])


def contrib(src: baseprint.Author) -> DataElement:
    ret = DataElement(StartTag('contrib', {'contrib-type': 'author'}))
    if src.orcid:
        url = str(src.orcid)
        xml_stag = StartTag('contrib-id', {'contrib-id-type': 'orcid'})
        ret.append(MarkupElement(xml_stag, url))
    name = DataElement('name')
    if src.surname:
        name.append(MarkupElement('surname', src.surname))
    if src.given_names:
        name.append(MarkupElement('given-names', src.given_names))
    ret.append(name)
    if src.email:
        ret.append(MarkupElement('email', src.email))
    return ret


def contrib_group(src: list[baseprint.Author]) -> DataElement:
    ret = DataElement('contrib-group')
    for a in src:
        ret.append(contrib(a))
    return ret


def proto_section(
        tag: str, src: baseprint.ProtoSection, title: MixedContent | None = None
) -> DataElement:
    ret = DataElement(tag)
    if title is not None:
        t = MarkupElement('title', title)
        ret.append(t)
    for e in src.presection:
        ret.append(e)
    for ss in src.subsections:
        ret.append(proto_section('sec', ss, ss.title))
    return ret


def abstract(src: baseprint.Abstract) -> DataElement:
    return proto_section('abstract', src)


def article(src: baseprint.Baseprint) -> DataElement:
    ret = DataElement('article', [
        DataElement('front', [
            DataElement('article-meta', [
                title_group(src.title),
                contrib_group(src.authors),
                abstract(src.abstract),
            ])
        ]),
        proto_section('body', src.body),
    ])
    return ret

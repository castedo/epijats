from __future__ import annotations

import os
from pathlib import Path

from lxml import etree

from . import baseprint
from .tree import DataElement, MarkupElement, MixedContent, StartTag
from .xml import data_element


def title_group(src: MixedContent) -> DataElement:
    title = MarkupElement('article-title', src.text)
    for it in src:
        title.content.append(it)
    return DataElement('title-group', [title])


def person_name(src: baseprint.PersonName) -> DataElement:
    ret = DataElement('name')
    if src.surname:
        ret.append(MarkupElement('surname', src.surname))
    if src.given_names:
        ret.append(MarkupElement('given-names', src.given_names))
    return ret


def contrib(src: baseprint.Author) -> DataElement:
    ret = DataElement(StartTag('contrib', {'contrib-type': 'author'}))
    if src.orcid:
        url = str(src.orcid)
        xml_stag = StartTag('contrib-id', {'contrib-id-type': 'orcid'})
        ret.append(MarkupElement(xml_stag, url))
    ret.append(person_name(src.name))
    if src.email:
        ret.append(MarkupElement('email', src.email))
    return ret


def contrib_group(src: list[baseprint.Author]) -> DataElement:
    ret = DataElement('contrib-group')
    for a in src:
        ret.append(contrib(a))
    return ret


def proto_section(
        tag: str,
        src: baseprint.ProtoSection,
        xid: str | None = None,
        title: MixedContent | None = None,
) -> DataElement:
    ret = DataElement(tag)
    if xid is not None:
        ret.xml.attrib['id'] = xid
    if title is not None:
        t = MarkupElement('title', title)
        ret.append(t)
    for e in src.presection:
        ret.append(e)
    for ss in src.subsections:
        ret.append(proto_section('sec', ss, ss.id, ss.title))
    return ret


def abstract(src: baseprint.Abstract) -> DataElement:
    return proto_section('abstract', src)


def ref_list(src: baseprint.RefList) -> DataElement:
    ret = DataElement('ref-list', [])
    if src.title is not None:
        ret.append(MarkupElement('title', src.title))
    return ret


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
    if src.ref_list is not None:
        ret.append(DataElement('back', [ref_list(src.ref_list)]))
    return ret


def write_baseprint(src: baseprint.Baseprint, dest: Path) -> None:
    root = data_element(article(src), 0)
    root.tail = "\n"
    os.makedirs(dest, exist_ok=True)
    with open(dest / "article.xml", "wb") as f:
        etree.ElementTree(root).write(f)

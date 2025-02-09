from __future__ import annotations

import os
from pathlib import Path

from lxml import etree

from . import baseprint
from .tree import DataElement, MarkupElement, MixedContent, StartTag
from .xml import xml_element


def markup_element(tag: str, src: MixedContent) -> MarkupElement:
    ret = MarkupElement(tag, src.text)
    for it in src:
        ret.content.append(it)
    return ret


def title_group(src: MixedContent) -> DataElement:
    title = markup_element('article-title', src)
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


def license(src: baseprint.License) -> DataElement:
    ret = DataElement('license')
    license_ref = MarkupElement("{http://www.niso.org/schemas/ali/1.0/}license_ref")
    license_ref.content.text = src.license_ref
    if src.cc_license_type:
        license_ref.xml.attrib['content-type'] = src.cc_license_type
    ret.append(license_ref)
    ret.append(MarkupElement('license-p', src.license_p))
    return ret


def permissions(src: baseprint.Permissions) -> DataElement:
    ret = DataElement('permissions')
    if src.copyright is not None:
        ret.append(MarkupElement('copyright-statement', src.copyright.statement))
    if src.license is not None:
        ret.append(license(src.license))
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


def biblio_ref(src: baseprint.BiblioReference) -> DataElement:
    stag = StartTag('element-citation', {'publication-type': src.publication_type})
    ec = DataElement(stag)
    if src.authors:
        pg = DataElement(StartTag('person-group', {'person-group-type': 'author'}))
        for a in src.authors:
            if isinstance(a, baseprint.PersonName):
                pg.append(person_name(a))
            else:
                pg.append(MarkupElement('string-name', a))
        ec.append(pg)
    if src.year is not None:
        y = str(src.year)
        ec.append(MarkupElement(StartTag('year', {'iso-8601-date': y}), y))
    if src.article_title:
        ec.append(markup_element('article-title', src.article_title))
    for key, value in src.biblio_fields.items():
        ec.append(MarkupElement(key, value))
    ret = DataElement('ref', [ec])
    ret.xml.attrib['id'] = src.id
    return ret


def ref_list(src: baseprint.RefList) -> DataElement:
    ret = DataElement('ref-list', [])
    if src.title is not None:
        ret.append(MarkupElement('title', src.title))
    for ref in src.references:
        ret.append(biblio_ref(ref))
    return ret


def article(src: baseprint.Baseprint) -> DataElement:
    article_meta = DataElement('article-meta', [
                title_group(src.title),
                contrib_group(src.authors),
    ])
    if src.permissions:
        article_meta.append(permissions(src.permissions))
    article_meta.append(abstract(src.abstract))
    ret = DataElement('article', [
        DataElement('front', [article_meta]),
        proto_section('body', src.body),
    ])
    if src.ref_list is not None:
        ret.append(DataElement('back', [ref_list(src.ref_list)]))
    return ret


def write_baseprint(src: baseprint.Baseprint, dest: Path) -> None:
    root = xml_element(article(src))
    root.tail = "\n"
    os.makedirs(dest, exist_ok=True)
    with open(dest / "article.xml", "wb") as f:
        etree.ElementTree(root).write(f)

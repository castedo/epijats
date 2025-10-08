from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
from warnings import warn

from .. import dom
from ..document import Abstract
from ..metadata import BiblioRefItem, Date
from ..parse import parse_baseprint
from ..parse.kit import Log, nolog
from ..tree import (
    DataElement,
    ArrayContent,
    MarkupElement,
    MixedContent,
    StartTag,
    WhitespaceElement,
)
from .format import XmlFormatter

if TYPE_CHECKING:
    from ..typeshed import StrPath


def title_group(src: MixedContent | None) -> DataElement:
    # space prevents self-closing XML syntax
    text = ' ' if src is None else src.text
    title = MarkupElement('article-title', text)
    if src:
        for it in src:
            title.content.append(it)
    return DataElement('title-group', [title])


def person_name(src: dom.PersonName) -> DataElement:
    ret = DataElement('name')
    if src.surname:
        ret.content.append(MarkupElement('surname', src.surname))
    if src.given_names:
        ret.content.append(MarkupElement('given-names', src.given_names))
    if src.suffix:
        ret.content.append(MarkupElement('suffix', src.suffix))
    return ret


def contrib(src: dom.Author) -> DataElement:
    ret = DataElement(StartTag('contrib', {'contrib-type': 'author'}))
    if src.orcid:
        url = str(src.orcid)
        xml_stag = StartTag('contrib-id', {'contrib-id-type': 'orcid'})
        ret.content.append(MarkupElement(xml_stag, url))
    ret.content.append(person_name(src.name))
    if src.email:
        ret.content.append(MarkupElement('email', src.email))
    return ret


def contrib_group(src: list[dom.Author]) -> DataElement:
    ret = DataElement('contrib-group')
    for a in src:
        ret.content.append(contrib(a))
    return ret


def license(src: dom.License) -> DataElement:
    ret = DataElement('license')
    license_ref = MarkupElement("license-ref")
    license_ref.content.text = src.license_ref
    if src.cc_license_type:
        license_ref.xml.attrib['content-type'] = src.cc_license_type
    ret.content.append(license_ref)
    ret.content.append(MarkupElement('license-p', src.license_p))
    return ret


def permissions(src: dom.Permissions) -> DataElement:
    ret = DataElement('permissions')
    if src.copyright is not None:
        ret.content.append(MarkupElement('copyright-statement', src.copyright.statement))
    if src.license is not None:
        ret.content.append(license(src.license))
    return ret


def proto_section(
    tag: str,
    src: dom.ProtoSection,
    level: int,
    xid: str | None = None,
    title: MixedContent | None = None,
) -> DataElement:
    if level < 6:
        level += 1
    ret = DataElement(tag)
    if xid is not None:
        ret.xml.attrib['id'] = xid
    if title is not None:
        t = MarkupElement(f"h{level}", title)
        ret.content.append(t)
    ret.content.extend(src.presection)
    for ss in src.subsections:
        ret.content.append(proto_section('section', ss, level, ss.id, ss.title))
    return ret


def abstract(src: Abstract) -> DataElement:
    return DataElement('abstract', src.blocks)


def append_date_parts(src: Date | None, dest: ArrayContent) -> None:
    if src is not None:
        y = str(src.year)
        dest.append(MarkupElement('year', y))
        if src.month is not None:
            # zero padding is more common in PMC citations
            # some JATS parsers (like pandoc) expect zero padding
            dest.append(MarkupElement('month', f"{src.month:02}"))
            if src.day is not None:
                dest.append(MarkupElement('day', f"{src.day:02}"))


def biblio_person_group(group_type: str, src: dom.PersonGroup) -> DataElement:
    ret = DataElement(StartTag('person-group', {'person-group-type': group_type}))
    for person in src.persons:
        if isinstance(person, dom.PersonName):
            ret.content.append(person_name(person))
        else:
            ret.content.append(MarkupElement('string-name', person))
    if src.etal:
        # <etal> is not an HTML void element.
        # If it is saved as a self-closing XML element, an HTML parser
        # will not close the element until the next open tag
        # (probably merely resulting in whitespace content being added).
        ret.content.append(WhitespaceElement('etal'))
    return ret


def biblio_ref_item(src: BiblioRefItem) -> DataElement:
    stag = StartTag('element-citation')
    ec = DataElement(stag)
    if src.authors:
        ec.content.append(biblio_person_group('author', src.authors))
    if src.editors:
        ec.content.append(biblio_person_group('editor', src.editors))
    if src.article_title:
        ec.content.append(MarkupElement('article-title', src.article_title))
    if src.source_title:
        ec.content.append(MarkupElement('source-title', src.source_title))
    if src.edition is not None:
        ec.content.append(MarkupElement('edition', str(src.edition)))
    append_date_parts(src.date, ec.content)
    if src.access_date:
        ad = DataElement(StartTag('date-in-citation', {'content-type': 'access-date'}))
        append_date_parts(src.access_date, ad.content)
        ec.content.append(ad)
    for key, value in src.biblio_fields.items():
        ec.content.append(MarkupElement(key, value))
    for pub_id_type, value in src.pub_ids.items():
        ele = MarkupElement('pub-id', value)
        ele.xml.attrib['pub-id-type'] = pub_id_type
        ec.content.append(ele)
    ret = DataElement('ref', [ec])
    ret.xml.attrib['id'] = src.id
    return ret


def ref_list(src: dom.BiblioRefList) -> DataElement:
    ret = DataElement('ref-list', [])
    for ref in src.references:
        ret.content.append(biblio_ref_item(ref))
    return ret


def article(src: dom.Article) -> DataElement:
    article_meta = DataElement('article-meta')
    if src.title:
        article_meta.content.append(title_group(src.title))
    if src.authors:
        article_meta.content.append(contrib_group(src.authors))
    if src.permissions:
        article_meta.content.append(permissions(src.permissions))
    if src.abstract:
        article_meta.content.append(abstract(src.abstract))
    ret = DataElement('article')
    if len(article_meta.content):
        ret.content.append(DataElement('front', [article_meta]))
    if src.body.has_content(): 
        ret.content.append(proto_section('article-body', src.body, 0))
    if src.ref_list is not None:
        ret.content.append(DataElement('back', [ref_list(src.ref_list)]))
    return ret


def write_baseprint(
    src: dom.Article, dest: StrPath, *, use_lxml: bool = False
) -> None:
    if use_lxml:
        warn("Avoid depending on lxml specific behavior", DeprecationWarning)
    XML = XmlFormatter(use_lxml=use_lxml)
    root = XML.root(article(src))
    root.tail = "\n"
    os.makedirs(dest, exist_ok=True)
    with open(Path(dest) / "article.xml", "wb") as f:
        tree = XML.ET.ElementTree(root)
        tree.write(f)


def restyle_xml(src_xml: StrPath, target_dir: StrPath, log: Log = nolog) -> bool:
    bdom = parse_baseprint(Path(src_xml), log)
    if bdom is None:
        return False
    write_baseprint(bdom, Path(target_dir))
    return True

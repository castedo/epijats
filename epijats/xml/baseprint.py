from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
from warnings import warn

from .. import dom
from ..document import Abstract
from ..metadata import BiblioRefItem, Date
from ..parse import parse_baseprint
from ..parse.kit import Log, Sink, nolog
from ..tree import (
    ArrayParent,
    Element,
    MixedContent,
    MixedParent,
    StartTag,
    WhitespaceElement,
)
from .format import XmlFormatter

if TYPE_CHECKING:
    from ..typeshed import StrPath


def title_group(src: MixedContent | None) -> ArrayParent:
    # space prevents self-closing XML syntax
    text = ' ' if src is None else src.text
    title = MixedParent('article-title', text)
    if src:
        for element, tail in src:
            title.append(element)
            title.append(tail)
    return ArrayParent('title-group', [title])


def person_name(src: dom.PersonName) -> ArrayParent:
    ret = ArrayParent('name')
    if src.surname:
        ret.append(MixedParent('surname', src.surname))
    if src.given_names:
        ret.append(MixedParent('given-names', src.given_names))
    if src.suffix:
        ret.append(MixedParent('suffix', src.suffix))
    return ret


def contrib(src: dom.Author) -> ArrayParent:
    ret = ArrayParent(StartTag('contrib', {'contrib-type': 'author'}))
    if src.orcid:
        url = str(src.orcid)
        xml_stag = StartTag('contrib-id', {'contrib-id-type': 'orcid'})
        ret.append(MixedParent(xml_stag, url))
    ret.append(person_name(src.name))
    if src.email:
        ret.append(MixedParent('email', src.email))
    return ret


def contrib_group(src: list[dom.Author]) -> ArrayParent:
    ret = ArrayParent('contrib-group')
    for a in src:
        ret.append(contrib(a))
    return ret


def license(src: dom.License) -> ArrayParent:
    ret = ArrayParent('license')
    attrib = {'content-type': src.cc_license_type} if src.cc_license_type else {}
    license_ref = MixedParent(StartTag("license-ref", attrib))
    license_ref.content.text = src.license_ref
    ret.append(license_ref)
    ret.append(MixedParent('license-p', src.license_p))
    return ret


def permissions(src: dom.Permissions) -> ArrayParent:
    ret = ArrayParent('permissions')
    if src.copyright is not None:
        ret.append(MixedParent('copyright-statement', src.copyright.statement))
    if src.license is not None:
        ret.append(license(src.license))
    return ret


def proto_section(
    tag: str,
    src: dom.ProtoSection,
    level: int,
    xid: str | None = None,
    title: MixedContent | None = None,
) -> ArrayParent:
    if level < 6:
        level += 1
    attrib = {} if xid is None else {'id': xid}
    ret = ArrayParent(StartTag(tag, attrib))
    if title is not None:
        t = MixedParent(f"h{level}", title)
        ret.append(t)
    for s in src.presection:
        ret.append(s)
    for ss in src.subsections:
        ret.append(proto_section('section', ss, level, ss.id, ss.title))
    return ret


def abstract(src: Abstract) -> ArrayParent:
    return ArrayParent('abstract', src.content)


def append_date_parts(src: Date | None, dest: Sink[Element]) -> None:
    if src is not None:
        y = str(src.year)
        dest(MixedParent('year', y))
        if src.month is not None:
            # zero padding is more common in PMC citations
            # some JATS parsers (like pandoc) expect zero padding
            dest(MixedParent('month', f"{src.month:02}"))
            if src.day is not None:
                dest(MixedParent('day', f"{src.day:02}"))


def biblio_person_group(group_type: str, src: dom.PersonGroup) -> ArrayParent:
    ret = ArrayParent(StartTag('person-group', {'person-group-type': group_type}))
    for person in src.persons:
        if isinstance(person, dom.PersonName):
            ret.append(person_name(person))
        else:
            ret.append(MixedParent('string-name', person))
    if src.etal:
        # <etal> is not an HTML void element.
        # If it is saved as a self-closing XML element, an HTML parser
        # will not close the element until the next open tag
        # (probably merely resulting in whitespace content being added).
        ret.append(WhitespaceElement('etal'))
    return ret


def biblio_ref_item(src: BiblioRefItem) -> ArrayParent:
    stag = StartTag('element-citation')
    ec = ArrayParent(stag)
    if src.authors:
        ec.append(biblio_person_group('author', src.authors))
    if src.editors:
        ec.append(biblio_person_group('editor', src.editors))
    if src.article_title:
        ec.append(MixedParent('article-title', src.article_title))
    if src.source_title:
        ec.append(MixedParent('source-title', src.source_title))
    if src.edition is not None:
        ec.append(MixedParent('edition', str(src.edition)))
    append_date_parts(src.date, ec.append)
    if src.access_date:
        ad = ArrayParent(StartTag('date-in-citation', {'content-type': 'access-date'}))
        append_date_parts(src.access_date, ad.append)
        ec.append(ad)
    for key, value in src.biblio_fields.items():
        ec.append(MixedParent(key, value))
    for pub_id_type, value in src.pub_ids.items():
        stag = StartTag('pub-id', {'pub-id-type': pub_id_type})
        ele = MixedParent(stag, value)
        ec.append(ele)
    ret = ArrayParent(StartTag('ref', {'id': src.id}), [ec])
    return ret


def ref_list(src: dom.BiblioRefList) -> ArrayParent:
    ret = ArrayParent('ref-list', [])
    for ref in src.references:
        ret.append(biblio_ref_item(ref))
    return ret


def article(src: dom.Article) -> ArrayParent:
    article_meta = ArrayParent('article-meta')
    if src.title:
        article_meta.append(title_group(src.title))
    if src.authors:
        article_meta.append(contrib_group(src.authors))
    if src.permissions:
        article_meta.append(permissions(src.permissions))
    if src.abstract:
        article_meta.append(abstract(src.abstract))
    ret = ArrayParent('article')
    if len(article_meta.content):
        ret.append(ArrayParent('front', [article_meta]))
    if src.body.has_content():
        ret.append(proto_section('article-body', src.body, 0))
    if src.ref_list is not None:
        ret.append(ArrayParent('back', [ref_list(src.ref_list)]))
    return ret


def write_baseprint(src: dom.Article, dest: StrPath, *, use_lxml: bool = False) -> None:
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

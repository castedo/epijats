from __future__ import annotations

import os
from pathlib import Path

from . import baseprint
from . import baseprint as bp
from .parse import parse_baseprint
from .parse.kit import Log, nolog
from .tree import DataElement, EmptyElement, MarkupElement, MixedContent, StartTag
from .xml import XmlFormatter


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
    if src.suffix:
        ret.append(MarkupElement('suffix', src.suffix))
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
    license_ref = MarkupElement("license-ref")
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
        ret.append(t)
    ret.extend(src.presection)
    for ss in src.subsections:
        ret.append(proto_section('section', ss, level, ss.id, ss.title))
    return ret


def abstract(src: baseprint.Abstract) -> DataElement:
    return DataElement('abstract', src.blocks)


def append_date_parts(src: baseprint.Date | None, dest: DataElement) -> None:
    if src is not None:
        y = str(src.year)
        dest.append(MarkupElement('year', y))
        if src.month is not None:
            # zero padding is more common in PMC citations
            # some JATS parsers (like pandoc) expect zero padding
            dest.append(MarkupElement('month', f"{src.month:02}"))
            if src.day is not None:
                dest.append(MarkupElement('day', f"{src.day:02}"))


def biblio_person_group(group_type: str, src: bp.PersonGroup) -> DataElement:
    ret = DataElement(StartTag('person-group', {'person-group-type': group_type}))
    for person in src.persons:
        if isinstance(person, bp.PersonName):
            ret.append(person_name(person))
        else:
            ret.append(MarkupElement('string-name', person))
    if src.etal:
        ret.append(EmptyElement('etal'))
    return ret


def biblio_ref_item(src: bp.BiblioRefItem) -> DataElement:
    stag = StartTag('element-citation')
    ec = DataElement(stag)
    if src.authors:
        ec.append(biblio_person_group('author', src.authors))
    if src.editors:
        ec.append(biblio_person_group('editor', src.editors))
    if src.article_title:
        ec.append(MarkupElement('article-title', src.article_title))
    if src.source_title:
        ec.append(MarkupElement('source-title', src.source_title))
    if src.edition is not None:
        ec.append(MarkupElement('edition', str(src.edition)))
    append_date_parts(src.date, ec)
    if src.access_date:
        ad = DataElement(StartTag('date-in-citation', {'content-type': 'access-date'}))
        append_date_parts(src.access_date, ad)
        ec.append(ad)
    for key, value in src.biblio_fields.items():
        ec.append(MarkupElement(key, value))
    for pub_id_type, value in src.pub_ids.items():
        ele = MarkupElement('pub-id', value)
        ele.xml.attrib['pub-id-type'] = pub_id_type
        ec.append(ele)
    ret = DataElement('ref', [ec])
    ret.xml.attrib['id'] = src.id
    return ret


def ref_list(src: baseprint.BiblioRefList) -> DataElement:
    ret = DataElement('ref-list', [])
    for ref in src.references:
        ret.append(biblio_ref_item(ref))
    return ret


def article(src: baseprint.Baseprint) -> DataElement:
    article_meta = DataElement('article-meta', [title_group(src.title)])
    if src.authors:
        article_meta.append(contrib_group(src.authors))
    if src.permissions:
        article_meta.append(permissions(src.permissions))
    if src.abstract:
        article_meta.append(abstract(src.abstract))
    ret = DataElement(
        'article',
        [
            DataElement('front', [article_meta]),
            proto_section('article-body', src.body, 0),
        ],
    )
    if src.ref_list is not None:
        ret.append(DataElement('back', [ref_list(src.ref_list)]))
    return ret


def write_baseprint(
    src: baseprint.Baseprint, dest: Path, *, use_lxml: bool = True
) -> None:
    XML = XmlFormatter(use_lxml=use_lxml)
    root = XML.root(article(src))
    root.tail = "\n"
    os.makedirs(dest, exist_ok=True)
    with open(dest / "article.xml", "wb") as f:
        tree = XML.ET.ElementTree(root)
        tree.write(f)


def restyle_xml(src_xml: Path | str, target_dir: Path | str, log: Log = nolog) -> bool:
    bdom = parse_baseprint(Path(src_xml), log)
    if bdom is None:
        return False
    write_baseprint(bdom, Path(target_dir))
    return True

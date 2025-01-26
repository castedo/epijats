from __future__ import annotations

from . import baseprint
from .tree import DataElement, Element, ElementContent, MarkupElement, MixedContent, StartTag


def sub_element(src: Element) -> Element:
    if isinstance(src, MarkupElement) and src.data_model:
        ret = DataElement(src.xml.tag)
        ret.xml.attrib = src.xml.attrib
        data_content(src.content, ret)
        ret.tail = src.tail
        return ret
    else:
        return src

def element(src: Element) -> Element:
    if isinstance(src, DataElement):
        return src
    ret: DataElement | MarkupElement
    if src.data_model:
        assert isinstance(src, MarkupElement)
        ret = DataElement(src.xml)
        data_content(src.content, ret)
    else:
        # assert not src.tail
        assert isinstance(src, MarkupElement)
        ret = MarkupElement(src.xml, src.content.text)
        ret.block_level = src.block_level
        for it in src.content:
            ret.content.append(sub_element(it))
    return ret


def data_content(src: ElementContent, dest: DataElement) -> None:
    assert src.data_model
    assert not src.text
    for it in src:
        # assert not it.tail
        dest.append(element(it))


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


def proto_section(tag: str, src: baseprint.ProtoSection) -> DataElement:
    ret = DataElement(tag)
    for e in src.presection:
        ret.append(element(e))
#    for ss in src.subsections:
#        ret.append(sub)
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

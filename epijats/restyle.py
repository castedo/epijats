from __future__ import annotations

from . import baseprint
from .tree import DataElement, DataSubElement, MarkupElement, MarkupSubElement


def sub_element(src: baseprint.SubElement) -> MarkupSubElement | DataSubElement:
    ret: MarkupSubElement | DataSubElement
    if src.data_model:
        ret = DataSubElement(src.xml_tag, src.xml_attrib)
        data_content(src, ret)
    else:
        ret = MarkupSubElement(src.xml_tag, src.xml_attrib, src.text)
        for it in src:
            ret.append(sub_element(it))
    ret.tail = src.tail
    return ret


def element(src: baseprint.SubElement) -> DataElement | MarkupElement:
    ret: DataElement | MarkupElement
    if src.data_model:
        ret = DataElement(src.xml_tag, src.xml_attrib)
        data_content(src, ret)
    else:
        # assert not src.tail
        ret = MarkupElement(src.xml_tag, src.xml_attrib, src.text)
        for it in src:
            ret.append(sub_element(it))
    return ret


def data_content(src: baseprint.ElementContent, dest: DataElement) -> None:
    assert src.data_model
    assert not src.text
    for it in src:
        # assert not it.tail
        dest.append(element(it))
        if not it.data_model:
            dest.indent = False


def title_group(src: baseprint.ElementContent) -> DataElement:
    title = MarkupElement('article-title', {}, src.text)
    for it in src:
        title.append(sub_element(it))
    return DataElement('title-group', {}, [title])


def contrib(src: baseprint.Author) -> DataElement:
    ret = DataElement('contrib', {'contrib-type': 'author'})
    if src.orcid:
        url = str(src.orcid)
        ret.append(MarkupElement('contrib-id', {'contrib-id-type': 'orcid'}, url))
    name = DataElement('name')
    if src.surname:
        name.append(MarkupElement('surname', {}, src.surname))
    if src.given_names:
        name.append(MarkupElement('given-names', {}, src.given_names))
    ret.append(name)
    if src.email:
        ret.append(MarkupElement('email', {}, src.email))
    return ret


def contrib_group(src: list[baseprint.Author]) -> DataElement:
    ret = DataElement('contrib-group', {})
    for a in src:
        ret.append(contrib(a))
    return ret


def proto_section(tag: str, src: baseprint.ProtoSection) -> DataElement:
    ret = DataElement(tag)
    ret.indent = False
    data_content(src.presection, ret)
#    for ss in src.subsections:
#        ret.append(sub)
    return ret


def abstract(src: baseprint.Abstract) -> DataElement:
    return proto_section('abstract', src)


def article(src: baseprint.Baseprint) -> DataElement:
    ret = DataElement('article', {}, [
        DataElement('front', {}, [
            DataElement('article-meta', {}, [
                title_group(src.title),
                contrib_group(src.authors),
                abstract(src.abstract),
            ])
        ]),
        proto_section('body', src.body),
    ])
    return ret

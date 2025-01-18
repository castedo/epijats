from __future__ import annotations

from typing import TYPE_CHECKING

from lxml.builder import ElementMaker

if TYPE_CHECKING:
    from lxml.etree import _Element

from .baseprint import Abstract, Author, Baseprint, ElementContent, List, SubElement


E = ElementMaker(
    nsmap={
        'ali': "http://www.niso.org/schemas/ali/1.0",
        'mml': "http://www.w3.org/1998/Math/MathML",
        'xlink': "http://www.w3.org/1999/xlink",
    }
)


def EL(tag: str, level: int, *children: str | _Element, **attrib: str) -> _Element:
    newline = "\n" + "  " * level
    chunks = [txt for chil in children for txt in ("  ", chil, newline)]
    return E(tag, newline, *chunks, **attrib)


class DataElement:
    def __init__(self, tag: str, level: int = 0, **attrib: str):
        self.level = level
        self.tag = tag
        self.attrib = attrib
        self.children: list[_Element | DataElement] = []

    def append_data(self, tag: str, **attrib: str) -> DataElement:
        ret = DataElement(tag, self.level + 1, **attrib)
        self.children.append(ret)
        return ret

    def append_content(self, e: _Element) -> None:
        self.children.append(e)

    def build(self) -> _Element:
        elements = []
        for c in self.children:
            elements.append(c.build() if isinstance(c, DataElement) else c)
        return EL(self.tag, self.level, *elements, **self.attrib)


def baseprint_to_xml(src: Baseprint) -> _Element:
    article = DataElement('article')
    front = article.append_data('front')

    am = front.append_data('article-meta')
    title_group(am, src.title)
    contrib_group(am, src.authors)
    am.append_content(abstract(src.abstract))

    article.append_content(E('body'))
    ret = article.build()
    ret.tail = "\n"
    return ret


def title_group(parent: DataElement, title: ElementContent) -> None:
    r = parent.append_data('title-group')
    r.append_content(E('article-title', *content(title)))


def contrib_group(parent: DataElement, src: list[Author]) -> None:
    cg = parent.append_data('contrib-group')
    for a in src:
        author(cg, a)


def author(parent: DataElement, src: Author) -> None:
    c = parent.append_data('contrib', **{'contrib-type': 'author'})
    n = c.append_data('name')
    if src.surname:
        n.append_content(E('surname', src.surname))
    if src.given_names:
        n.append_content(E('given-names', src.given_names))


def abstract(src: Abstract | None) -> _Element:
    ret = E('abstract')
    if src is not None:
        for p in src.paragraphs:
            ret.append(E('p', *content(p)))
    return ret


def sub_element(src: SubElement) -> _Element:
    ret: _Element
    if isinstance(src, List):
        data = DataElement('list', 0, **{'list-type': 'bullet'})
        for it in src.items:
            data.append_content(sub_element(it))
        ret = data.build()
    else:
        ret = E(src.xml_tag, *content(src), **src.xml_attrib)
    ret.tail = src.tail
    return ret


def content(ec: ElementContent) -> list[str | _Element]:
    ret: list[str | _Element] = [ec.text]
    for sub in ec:
        ret.append(sub_element(sub))
    return ret

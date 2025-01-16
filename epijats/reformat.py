from __future__ import annotations

from lxml import etree
from lxml.builder import ElementMaker

from .baseprint import Abstract, Author, Baseprint


E = ElementMaker(nsmap={
    'ali': "http://www.niso.org/schemas/ali/1.0",
    'mml': "http://www.w3.org/1998/Math/MathML",
    'xlink': "http://www.w3.org/1999/xlink",
})


def baseprint_to_xml(src: Baseprint) -> etree._Element:
    front = E('front',
        E('article-meta',
            E('title-group', E('article-title', src.title.text)), 
            contrib_group(src.authors),            
            abstract(src.abstract), 
        )
    )
    body = E('body')
    ret = E('article', front, body)
    etree.indent(ret)
    ret.tail = "\n"
    return ret


def contrib_group(src: list[Author]) -> etree._Element:
    ret = E('contrib-group')
    for author in src:
        name = E('name')
        if author.surname:
            name.append(E('surname', author.surname))
        if author.given_names:
            name.append(E('surname', author.given_names))
        contrib = E('contrib', name, **{'contrib-type': 'author'})
        ret.append(contrib)
    return ret


def abstract(src: Abstract | None) -> etree._Element:
    return E('abstract')

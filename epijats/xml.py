from __future__ import annotations

from typing import TYPE_CHECKING

from lxml.builder import ElementMaker

if TYPE_CHECKING:
    from lxml.etree import _Element

from .tree import DataElement, MarkupElement


E = ElementMaker(
    nsmap={
        'ali': "http://www.niso.org/schemas/ali/1.0",
        'mml': "http://www.w3.org/1998/Math/MathML",
        'xlink': "http://www.w3.org/1999/xlink",
    }
)


def markup_element(src: MarkupElement) -> _Element:
    ret = E(src.xml_tag, **src.xml_attrib)
    ret.text = src.text
    for it in src:
        if isinstance(it, DataElement):
            sub = data_element(it, 0)
            sub.tail = "\n"
        else:
            sub = markup_element(it)
            sub.tail = it.tail
        ret.append(sub)
    return ret


def data_element(src: DataElement, level: int) -> _Element:
    ret = E(src.xml_tag, **src.xml_attrib)
    ret.text = "\n" + "  " * level
    presub = "\n"
    if src.indent:
        presub += "  " * (level + 1)
    sub: _Element | None = None
    for it in src:
        if isinstance(it, DataElement):
            sub = data_element(it, level + 1)
        else:
            sub = markup_element(it)
        sub.tail = presub
        ret.append(sub)
    if sub is not None:
        sub.tail = ret.text
        ret.text = presub
    return ret

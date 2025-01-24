from __future__ import annotations

from typing import TYPE_CHECKING

from lxml.builder import ElementMaker

if TYPE_CHECKING:
    from lxml.etree import _Element

from .tree import DataContent, MarkupContent


E = ElementMaker(
    nsmap={
        'ali': "http://www.niso.org/schemas/ali/1.0",
        'mml': "http://www.w3.org/1998/Math/MathML",
        'xlink': "http://www.w3.org/1999/xlink",
    }
)


def markup_content(src: MarkupContent) -> _Element:
    ret = E(src.xml_tag, src.text, **src.xml_attrib)
    for it in src:
        sub = markup_content(it)
        sub.tail = it.tail
        ret.append(sub)
    return ret


def data_content(src: DataContent, level: int) -> _Element:
    ret = E(src.xml_tag, **src.xml_attrib)
    ret.text = "\n" + "  " * level
    sub: _Element | None = None
    for it in src:
        if isinstance(it, DataContent):
            sub = data_content(it, level + 1)
        else:
            sub = markup_content(it)
        sub.tail = "\n" + "  " * (level + 1)
        ret.append(sub)
    if sub is not None:
        ret.text = "\n" + "  " * (level + 1)
        sub.tail = "\n" + "  " * level
    return ret

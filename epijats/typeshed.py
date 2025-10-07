from typing import TypeAlias

import _typeshed
import xml.etree.ElementTree

import lxml.etree


StrPath = _typeshed.StrPath  # (os.PathLike[str] | str)

JsonData: TypeAlias = (
    None | str | int | float | list['JsonData'] | dict[str, 'JsonData']
)

XmlElement: TypeAlias = lxml.etree._Element | xml.etree.ElementTree.Element

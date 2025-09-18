from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator


@dataclass
class StartTag:
    tag: str
    attrib: dict[str, str]

    def __init__(self, tag: str | StartTag, attrib: dict[str, str] = {}):
        if isinstance(tag, str):
            self.tag = tag
            self.attrib = attrib.copy()
        else:
            self.tag = tag.tag
            self.attrib = tag.attrib | attrib


@dataclass
class PureElement:
    xml: StartTag

    def __init__(self, xml_tag: str | StartTag):
        self.xml = StartTag(xml_tag)

    def __iter__(self) -> Iterator[PureElement]:
        return iter(())


@dataclass
class Element(PureElement):
    tail: str

    def __init__(self, xml_tag: str | StartTag):
        super().__init__(xml_tag)
        self.tail = ""


@dataclass
class MixedContent:
    text: str
    _children: list[Element]

    def __init__(self, content: str | MixedContent | Iterable[Element] = ""):
        super().__init__()
        if isinstance(content, str):
            self.text = content
            self._children = []
        elif isinstance(content, MixedContent):
            self.text = content.text
            self._children = list(content)
        else:
            self.text = ""
            self._children = list(content)

    def __iter__(self) -> Iterator[Element]:
        return iter(self._children)

    def append(self, e: Element) -> None:
        self._children.append(e)

    def append_text(self, s: str | None) -> None:
        if s:
            if self._children:
                self._children[-1].tail += s
            else:
                self.text += s

    def empty(self) -> bool:
        return not self._children and not self.text

    def blank(self) -> bool:
        return not self._children and not self.text.strip()


@dataclass
class MarkupElement(Element):
    _content: MixedContent

    def __init__(self, xml_tag: str | StartTag, content: str | MixedContent = ""):
        super().__init__(xml_tag)
        self._content = MixedContent(content)

    @property
    def content(self) -> MixedContent:
        return self._content


class EmptyElement(Element): ...


@dataclass
class DataElement(Element):
    _array: list[PureElement]

    def __init__(
        self,
        xml_tag: str | StartTag,
        array: Iterable[PureElement] = [],
    ):
        super().__init__(xml_tag)
        self._array = list(array)

    def __iter__(self) -> Iterator[PureElement]:
        return iter(self._array)

    def append(self, e: PureElement) -> None:
        self._array.append(e)

    def extend(self, es: Iterable[PureElement]) -> None:
        self._array.extend(es)


@dataclass
class Citation(MarkupElement):
    def __init__(self, rid: str, rord: int):
        super().__init__(StartTag('xref', {'rid': rid, 'ref-type': 'bibr'}))
        self.rid = rid
        self.rord = rord
        self.content.append_text(str(rord))

    def matching_text(self, text: str | None) -> bool:
        return text is not None and text.strip() == self.content.text


@dataclass
class CitationTuple(Element):
    _citations: list[Citation]

    def __init__(self, citations: Iterable[Citation] = ()) -> None:
        super().__init__('sup')
        self._citations = list(citations)

    def __iter__(self) -> Iterator[Element]:
        return iter(self._citations)

    def append(self, c: Citation) -> None:
        self._citations.append(c)

    def extend(self, cs: Iterable[Citation]) -> None:
        self._citations.extend(cs)

    def __len__(self) -> int:
        return len(self._citations)

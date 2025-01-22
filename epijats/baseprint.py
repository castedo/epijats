from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator


@dataclass
class ElementContent:
    text: str
    _subelements: list[SubElement]

    def __init__(self, text: str, elements: Iterable[SubElement]):
        self.text = text
        self._subelements = list(elements)
        self.data_model = False

    def __iter__(self) -> Iterator[SubElement]:
        return iter(self._subelements)

    def append(self, e: SubElement) -> None:
        self._subelements.append(e)

    def extend(self, es: Iterator[SubElement]) -> None:
        self._subelements.extend(es)

    def append_text(self, s: str | None) -> None:
        if s:
            if self._subelements:
                self._subelements[-1].tail += s
            else:
                self.text += s

    def empty(self) -> bool:
        return not self.text and not self._subelements


@dataclass
class SubElement(ElementContent):
    """Common JATS/HTML element"""

    xml_tag: str
    html_tag: str
    tail: str

    def __init__(
        self,
        text: str,
        elements: Iterable[SubElement],
        xml_tag: str,
        html_tag: str,
        tail: str,
    ):
        super().__init__(text, elements)
        self.xml_tag = xml_tag
        self.html_tag = html_tag
        self.tail = tail

    @property
    def xml_attrib(self) -> dict[str, str]:
        return {}

    @property
    def html_attrib(self) -> dict[str, str]:
        return {}


@dataclass
class Hyperlink(SubElement):
    href: str

    def __init__(self, text: str, subs: Iterable[SubElement], tail: str, href: str):
        super().__init__(text, subs, 'ext-link', 'a', tail)
        self.href = href

    @property
    def xml_attrib(self) -> dict[str, str]:
        return {"{http://www.w3.org/1999/xlink}href": self.href}

    @property
    def html_attrib(self) -> dict[str, str]:
        return {'href': self.href}


class ListItem(SubElement):
    def __init__(self, text: str, elements: Iterable[SubElement]):
        super().__init__(text, elements, 'list-item', 'li', "")
        self.data_model = True


class List(SubElement):
    def __init__(self, items: Iterable[ListItem], tail: str):
        super().__init__("", items, 'list', 'ul', tail)
        self.data_model = True

    @property
    def xml_attrib(self) -> dict[str, str]:
        return {"list-type": "bullet"}

    @property
    def items(self) -> list[ListItem]:
        ret = []
        for sub in iter(self):
            assert isinstance(sub, ListItem)
            ret.append(sub)
        return ret


@dataclass(frozen=True)
class Orcid:
    isni: str

    @staticmethod
    def from_url(url: str) -> Orcid:
        url = url.removeprefix("http://orcid.org/")
        url = url.removeprefix("https://orcid.org/")
        isni = url.replace("-", "")
        ok = (
            len(isni) == 16
            and isni[:15].isdigit()
            and (isni[15].isdigit() or isni[15] == "X")
        )
        if not ok:
            raise ValueError()
        return Orcid(isni)

    def as_19chars(self) -> str:
        return "{}-{}-{}-{}".format(
            self.isni[0:4],
            self.isni[4:8],
            self.isni[8:12],
            self.isni[12:16],
        )

    def __str__(self) -> str:
        return "https://orcid.org/" + self.as_19chars()


@dataclass
class Author:
    surname: str | None
    given_names: str | None = None
    email: str | None = None
    orcid: Orcid | None = None

    def __post_init__(self) -> None:
        if not self.surname and not self.given_names:
            raise ValueError()


@dataclass
class ProtoSection:
    presection: ElementContent
    subsections: list[Section]


@dataclass
class Section(ProtoSection):
    title: ElementContent


@dataclass
class Abstract(ProtoSection):
    pass


@dataclass
class Baseprint:
    title: ElementContent
    authors: list[Author]
    abstract: Abstract | None = None
    body: ElementContent | None = None

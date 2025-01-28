from __future__ import annotations

from dataclasses import dataclass

from .tree import DataElement, Element, MixedContent, StartTag, MarkupElement


@dataclass
class Hyperlink(MarkupElement):
    def __init__(self, href: str):
        super().__init__('ext-link')
        self.xml.attrib = {"{http://www.w3.org/1999/xlink}href": href}
        self.html = StartTag('a', {'href': href})


class ListItem(DataElement):
    def __init__(self) -> None:
        super().__init__('list-item')
        self.html = StartTag('li')


class List(DataElement):
    def __init__(self) -> None:
        super().__init__('list')
        self.xml.attrib = {"list-type": "bullet"}
        self.html = StartTag('ul')
        self.block_level = True


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
    presection: list[Element]
    subsections: list[Section]

    def __init__(self) -> None:
        self.presection = []
        self.subsections = []

    def has_no_content(self) -> bool:
        return not len(self.presection) and not len(self.subsections)


@dataclass
class Section(ProtoSection):
    id: str | None
    title: MixedContent


class Abstract(ProtoSection):
    pass


@dataclass
class Baseprint:
    title: MixedContent
    authors: list[Author]
    abstract: Abstract
    body: ProtoSection

    def __init__(self) -> None:
        self.title = MixedContent()
        self.authors = []
        self.abstract = Abstract()
        self.body = ProtoSection()

from __future__ import annotations

from dataclasses import dataclass

from .tree import DataElement, Element, MixedContent, StartTag, MarkupElement


@dataclass
class Hyperlink(MarkupElement):
    def __init__(self, href: str):
        super().__init__('ext-link')
        self.xml.attrib = {
            "ext-link-type": "uri",
            "{http://www.w3.org/1999/xlink}href": href,
        }
        self.html = StartTag('a', {'href': href})


@dataclass
class CrossReference(MarkupElement):
    def __init__(self, name: str, ref_type: str | None):
        super().__init__('xref')
        self.xml.attrib = {"rid": name}
        if ref_type:
            self.xml.attrib['ref-type'] = ref_type    
        self.html = StartTag('a', {'href': "#" + name})


class ListItem(DataElement):
    def __init__(self) -> None:
        super().__init__('list-item')
        self.html = StartTag('li')


class List(DataElement):
    def __init__(self) -> None:
        super().__init__('list')
        self.xml.attrib = {"list-type": "bullet"}
        self.html = StartTag('ul')


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
class PersonName:
    surname: str | None
    given_names: str | None = None

    def __post_init__(self) -> None:
        if not self.surname and not self.given_names:
            raise ValueError()


@dataclass
class Author:
    name: PersonName
    email: str | None = None
    orcid: Orcid | None = None


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
class CitationAuthor:
    name: PersonName | None
    string_name: str | None


@dataclass
class BibliographicReference:
    article_title: MixedContent
    authors: list[CitationAuthor]
    fpage: int | None
    lpage: int | None
    issue: int | None
    source: str | None
    uri: str | None
    volume: int | None
    year: int | None


@dataclass
class RefList:
    title: MixedContent | None
    references: list[BibliographicReference]

    def __init__(self, title: MixedContent | None = None) -> None:
        self.title = None
        self.references = []


@dataclass
class Baseprint:
    title: MixedContent
    authors: list[Author]
    abstract: Abstract
    body: ProtoSection
    ref_list: RefList | None

    def __init__(self) -> None:
        self.title = MixedContent()
        self.authors = []
        self.abstract = Abstract()
        self.body = ProtoSection()
        self.ref_list = None

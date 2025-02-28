from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

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


class ListTypeCode(StrEnum):
    BULLET = 'bullet'
    ORDER = 'order'


class List(DataElement):
    list_type: ListTypeCode | None

    def __init__(self, list_type: ListTypeCode | None) -> None:
        super().__init__('list')
        if list_type:
            self.xml.attrib['list-type'] = list_type
        if list_type == ListTypeCode.ORDER:
            self.html = StartTag('ol')
        else:
            self.html = StartTag('ul')


class AlignCode(StrEnum):
    LEFT = 'left'
    CENTER = 'center'
    RIGHT = 'right'


class TableCell(MarkupElement):
    def __init__(self, header: bool, align: AlignCode | None):
        super().__init__('th' if header else 'td')
        if align:
            self.xml.attrib['align'] = align
        self.html = StartTag(self.xml.tag)


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
class Copyright:
    statement: MixedContent


class CcLicenseType(StrEnum):
    CC0 = 'cc0license'
    BY = 'ccbylicense'
    BYSA = 'ccbysalicense'
    BYNC = 'ccbynclicense'
    BYNCSA = 'ccbyncsalicense'
    BYND = 'ccbyndlicense'
    BYNCND = 'ccbyncndlicense'


@dataclass
class License:
    license_p: MixedContent
    license_ref: str
    cc_license_type: CcLicenseType | None

    def blank(self) -> bool:
        return (
            self.license_p.blank()
            and not self.license_ref
            and self.cc_license_type is None
        )


@dataclass
class Permissions:
    license: License
    copyright: Copyright | None = None


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
class Date:
    year: int
    month: int | None = None
    day: int | None = None


class PubIdType(StrEnum):
    DOI = 'doi'
    PMID = 'pmid'


@dataclass
class BiblioRefItem:
    id: str
    authors: list[PersonName | str]
    editors: list[PersonName | str]
    article_title: str | None
    source: str | None
    edition: int | None
    date: Date | None
    access_date: Date | None
    biblio_fields: dict[str, str]
    pub_ids: dict[PubIdType, str]

    BIBLIO_FIELD_KEYS: ClassVar[list[str]] = [
        'volume',
        'issue',
        'publisher-name',
        'publisher-loc',
        'fpage',
        'lpage',
        'isbn',
        'issn',
        'uri',
        'comment',
    ]

    def __init__(self) -> None:
        self.id = ""
        self.authors = []
        self.editors = []
        self.article_title = None
        self.source = None
        self.edition = None
        self.date = None
        self.access_date = None
        self.biblio_fields = {}
        self.pub_ids = {}


@dataclass
class BiblioRefList:
    title: MixedContent | None
    references: list[BiblioRefItem]


@dataclass
class Baseprint:
    title: MixedContent
    authors: list[Author]
    abstract: Abstract
    permissions: Permissions | None
    body: ProtoSection
    ref_list: BiblioRefList | None

    def __init__(self) -> None:
        self.title = MixedContent()
        self.authors = []
        self.permissions = None
        self.abstract = Abstract()
        self.body = ProtoSection()
        self.ref_list = None

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Iterable

from .tree import MixedContent


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
    suffix: str | None = None

    def __post_init__(self) -> None:
        if not self.surname and not self.given_names:
            raise ValueError()


@dataclass
class Author:
    name: PersonName
    email: str | None = None
    orcid: Orcid | None = None


@dataclass
class Date:
    year: int
    month: int | None = None
    day: int | None = None


class PubIdType(StrEnum):
    DOI = 'doi'
    PMID = 'pmid'


@dataclass
class PersonGroup:
    persons: list[PersonName | str]
    etal: bool

    def __init__(self) -> None:
        self.persons = []
        self.etal = False

    def empty(self) -> bool:
        return not self.persons and not self.etal

    def __bool__(self) -> bool:
        return not self.empty()


@dataclass
class Copyright:
    statement: MixedContent

    def __init__(self, statement: MixedContent | str = '') -> None:
        self.statement = MixedContent(statement)

    def blank(self) -> bool:
        return self.statement.blank()


class CcLicenseType(StrEnum):
    CC0 = 'cc0license'
    BY = 'ccbylicense'
    BYSA = 'ccbysalicense'
    BYNC = 'ccbynclicense'
    BYNCSA = 'ccbyncsalicense'
    BYND = 'ccbyndlicense'
    BYNCND = 'ccbyncndlicense'

    @staticmethod
    def from_url(url: str) -> CcLicenseType | None:
        for prefix, matching_type in _CC_URLS.items():
            if url.startswith(prefix):
                return matching_type
        return None


_CC_URLS = {
    'https://creativecommons.org/publicdomain/zero/': CcLicenseType.CC0,
    'https://creativecommons.org/licenses/by/': CcLicenseType.BY,
    'https://creativecommons.org/licenses/by-sa/': CcLicenseType.BYSA,
    'https://creativecommons.org/licenses/by-nc/': CcLicenseType.BYNC,
    'https://creativecommons.org/licenses/by-nc-sa/': CcLicenseType.BYNCSA,
    'https://creativecommons.org/licenses/by-nd/': CcLicenseType.BYND,
    'https://creativecommons.org/licenses/by-nc-nd/': CcLicenseType.BYNCND,
}


@dataclass
class License:
    license_p: MixedContent
    license_ref: str
    cc_license_type: CcLicenseType | None

    def __init__(self) -> None:
        self.license_p = MixedContent()
        self.license_ref = ''
        self.cc_license_type = None

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

    def blank(self) -> bool:
        return self.license.blank() and (not self.copyright or self.copyright.blank())


@dataclass
class BiblioRefItem:
    id: str
    authors: PersonGroup
    editors: PersonGroup
    article_title: str | None
    source_title: str | None
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
        self.authors = PersonGroup()
        self.editors = PersonGroup()
        self.article_title = None
        self.source_title = None
        self.edition = None
        self.date = None
        self.access_date = None
        self.biblio_fields = {}
        self.pub_ids = {}


@dataclass
class BiblioRefList:
    references: list[BiblioRefItem]

    def __init__(self, refs: Iterable[BiblioRefItem] = ()):
        self.references = list(refs)

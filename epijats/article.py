from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from .baseprint import (
    Abstract,
    Author,
    BiblioRefItem,
)
from .tree import Element, MixedContent


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
class ProtoSection:
    presection: list[Element]
    subsections: list[Section]

    def __init__(self) -> None:
        self.presection = []
        self.subsections = []

    def has_content(self) -> bool:
        return bool(self.presection) or bool(self.subsections)


class ArticleBody(ProtoSection):
    ...


@dataclass
class Section(ProtoSection):
    id: str | None
    title: MixedContent

    def __init__(self, id: str | None = None, title: MixedContent | str = ""):
        super().__init__()
        self.title = MixedContent(title)
        self.id = id


@dataclass
class BiblioRefList:
    references: list[BiblioRefItem]

    def __init__(self, refs: Iterable[BiblioRefItem] = ()):
        self.references = list(refs)


@dataclass
class Article:
    title: MixedContent | None
    authors: list[Author]
    abstract: Abstract | None
    permissions: Permissions | None
    body: ArticleBody
    ref_list: BiblioRefList | None

    def __init__(self) -> None:
        self.title = None
        self.authors = []
        self.permissions = None
        self.abstract = None
        self.body = ArticleBody()
        self.ref_list = None


@dataclass
class Document:
    def __init__(self) -> None:
        self.article = Article()

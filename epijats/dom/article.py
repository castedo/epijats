from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from ..baseprint import (
    Abstract,
    Author,
    BiblioRefItem,
    Permissions,
)
from ..tree import Element, MixedContent

from ..biblio import ref_item_from_csljson

if TYPE_CHECKING:
    from ..typeshed import JSONType as JsonData


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

    @staticmethod
    def from_csljson(csljson: JsonData) -> BiblioRefList | None:
        if not isinstance(csljson, list):
            return None
        ret = BiblioRefList()
        for j_item in csljson:
            if r_item := ref_item_from_csljson(j_item):
                ret.references.append(r_item)
        return ret


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

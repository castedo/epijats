from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .metadata import Author, BiblioRefList, Permissions
from .tree import Element, MixedContent, MutableArrayContent, MutableMixedContent


@dataclass
class Abstract:
    content: MutableArrayContent

    def __init__(self, blocks: Iterable[Element] = ()) -> None:
        self.content = MutableArrayContent(blocks)


@dataclass
class ProtoSection:
    presection: MutableArrayContent
    subsections: list[Section]

    def __init__(self) -> None:
        self.presection = MutableArrayContent()
        self.subsections = []

    def has_content(self) -> bool:
        return bool(self.presection) or bool(self.subsections)


class ArticleBody(ProtoSection): ...


@dataclass
class Section(ProtoSection):
    id: str | None
    title: MutableMixedContent

    def __init__(self, id: str | None = None, title: MixedContent | str = ""):
        super().__init__()
        self.title = MutableMixedContent(title)
        self.id = id


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

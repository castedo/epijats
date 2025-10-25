from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .metadata import Author, BiblioRefList, Permissions
from .tree import ArrayContent, Element, MixedContent


@dataclass
class Abstract:
    content: ArrayContent

    def __init__(self, blocks: Iterable[Element] = ()) -> None:
        self.content = ArrayContent(blocks)


@dataclass
class ProtoSection:
    presection: ArrayContent
    subsections: list[Section]

    def __init__(self) -> None:
        self.presection = ArrayContent()
        self.subsections = []

    def has_content(self) -> bool:
        return bool(self.presection) or bool(self.subsections)


class ArticleBody(ProtoSection): ...


@dataclass
class Section(ProtoSection):
    id: str | None
    title: MixedContent

    def __init__(self, id: str | None = None, title: MixedContent | str = ""):
        super().__init__()
        self.title = MixedContent(title)
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

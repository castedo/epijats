from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from .condition import FormatIssue
from .metadata import Author, BiblioRefList, Permissions
from .tree import Element, MixedContent, MutableArrayContent, MutableMixedContent


@dataclass
class Abstract:
    content: MutableArrayContent

    def __init__(self, blocks: Iterable[Element] = ()) -> None:
        self.content = MutableArrayContent(blocks)

    @property
    def issues(self) -> Iterator[FormatIssue]:
        return self.content.issues


@dataclass
class ProtoSection:
    presection: MutableArrayContent
    subsections: list[Section]

    def __init__(self) -> None:
        self.presection = MutableArrayContent()
        self.subsections = []

    def has_content(self) -> bool:
        return bool(self.presection) or bool(self.subsections)

    @property
    def issues(self) -> Iterator[FormatIssue]:
        yield from self.presection.issues
        for sub in self.subsections:
            yield from sub.issues


class ArticleBody(ProtoSection): ...


@dataclass
class Section(ProtoSection):
    id: str | None
    title: MutableMixedContent

    def __init__(self, id: str | None = None, title: MixedContent | str = ""):
        super().__init__()
        self.title = MutableMixedContent(title)
        self.id = id

    @property
    def issues(self) -> Iterator[FormatIssue]:
        yield from self.title.issues
        yield from super().issues


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

    @property
    def issues(self) -> Iterator[FormatIssue]:
        if self.title:
            yield from self.title.issues
        if self.abstract:
            yield from self.abstract.issues
        yield from self.body.issues


@dataclass
class Document:
    def __init__(self) -> None:
        self.article = Article()

from dataclasses import dataclass

from ..baseprint import (
    Abstract,
    ArticleBody,
    Author,
    BiblioRefList,
    Permissions,
)
from ..tree import MixedContent


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

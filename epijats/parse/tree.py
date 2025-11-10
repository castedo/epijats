"""Parsing of abstract systax tree elements in ..tree submodule."""

from __future__ import annotations

from abc import abstractmethod
from typing import Generic, TYPE_CHECKING, TypeVar

from .. import condition as fc
from ..elements import ElementT
from ..tree import (
    Element,
    MarkupBlock,
    Parent,
    MixedParent,
    StartTag,
)

from . import kit
from .content import (
    ContentModel,
    DataContentModel,
    MixedModel,
)
from .kit import Log, Model, Sink


if TYPE_CHECKING:
    from ..typeshed import XmlContent, XmlElement


class TrivialElementModel(kit.LoadModelBase[str]):
    def __init__(self, tag: str):
        self.tag = tag

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == self.tag

    def load(self, log: Log, xe: XmlElement) -> str | None:
        kit.check_no_attrib(log, xe)
        kit.check_no_content(log, xe)
        return self.tag


ElementCovT = TypeVar('ElementCovT', bound=Element, covariant=True)


class TagModel(Generic[ElementCovT]):
    def __init__(
        self,
        element_type: type[ElementCovT],
        *,
        tag: str | StartTag | None = None,
        optional_attrib: set[str] = set(),
        jats_name: str | None = None,
    ):
        self.element_type = element_type
        if tag is not None:
            self.tag = StartTag(tag)

            def factory() -> ElementCovT:
                return self.element_type(tag)

            self.factory = factory
        else:
            self.tag = StartTag(element_type.TAG)
            self.factory = self.element_type
        self._ok_attrib_keys = optional_attrib | set(self.tag.attrib.keys())
        self.jats_name = jats_name

    def match(self, xe: XmlElement) -> bool:
        if self.jats_name is not None and xe.tag == self.jats_name:
            return True
        return self.tag.issubset(xe)

    def start(self, log: Log, xe: XmlElement) -> ElementCovT | None:
        kit.check_no_attrib(log, xe, self._ok_attrib_keys)
        ret = self.factory()
        for key, value in xe.attrib.items():
            if key not in self._ok_attrib_keys:
                log(fc.UnsupportedAttribute.issue(xe, key))
            elif key not in self.tag.attrib:
                ret.set_attrib(key, value)
        return ret


class ElementLoadModelBase(kit.LoadModelBase[ElementT]):
    def __init__(self, tag_model: TagModel[ElementT]):
        self.tag_model = tag_model

    def match(self, xe: XmlElement) -> bool:
        return self.tag_model.match(xe)

    @abstractmethod
    def parse_content(self, log: Log, xc: XmlContent, dest: ElementT) -> None: ...

    def load(self, log: Log, xe: XmlElement) -> ElementT | None:
        ret = self.tag_model.start(log, xe)
        if ret is not None:
            self.parse_content(log, xe, ret)
        return ret


class EmptyElementModel(ElementLoadModelBase[ElementT]):
    def parse_content(self, log: Log, xc: XmlContent, dest: ElementT) -> None:
        kit.check_no_content(log, xc)


ArrayParentT = TypeVar('ArrayParentT', bound=Parent[Element])


class ArrayParentModel(ElementLoadModelBase[ArrayParentT]):
    def __init__(
        self, tag_model: TagModel[ArrayParentT], content_model: ContentModel[Element]
    ):
        super().__init__(tag_model)
        self.content_model = content_model

    def parse_content(self, log: Log, xc: XmlContent, dest: Parent[Element]) -> None:
        self.content_model.parse_content(log, xc, dest.append)


class DataParentModel(ElementLoadModelBase[Parent[ElementT]]):
    def __init__(
        self, tag_model: TagModel[Parent[ElementT]], child_model: Model[ElementT]
    ):
        super().__init__(tag_model)
        self.content_model = DataContentModel(child_model)

    def parse_content(self, log: Log, xc: XmlContent, dest: Parent[ElementT]) -> None:
        self.content_model.parse_content(log, xc, dest.append)


MixedParentT = TypeVar('MixedParentT', bound=Parent[str | Element])


class MixedParentModel(ElementLoadModelBase[MixedParentT]):
    def __init__(
        self,
        tag_model: TagModel[MixedParentT],
        content_model: ContentModel[str | Element],
    ):
        super().__init__(tag_model)
        self.content_model = content_model

    def parse_content(
        self, log: Log, xc: XmlContent, dest: Parent[str | Element]
    ) -> None:
        self.content_model.parse_content(log, xc, dest.append)


class MarkupBlockModel(MixedParentModel[MixedParent]):
    def __init__(self, inline_model: MixedModel):
        super().__init__(TagModel(MarkupBlock), inline_model)


class MixedContentInElementParser(kit.Model[str | Element]):
    def __init__(self, tag: str, content_model: ContentModel[str | Element]):
        self.content_model = content_model
        self.tag = tag

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == self.tag

    def parse(self, log: Log, xe: XmlElement, out: Sink[str | Element]) -> bool:
        kit.check_no_attrib(log, xe)
        self.content_model.parse_content(log, xe, out)
        return True

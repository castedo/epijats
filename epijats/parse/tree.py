"""Parsing of abstract systax tree elements in ..tree submodule."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from typing import Generic, TYPE_CHECKING

from .. import condition as fc
from ..elements import ElementT
from ..tree import (
    AppendT,
    ArrayParent,
    Element,
    MarkupBlock,
    MixedParent,
    Parent,
    StartTag,
)

from . import kit
from .content import (
    ContentModel,
    DataContentModel,
    MixedModel,
)
from .kit import Log, Model, ParsedT, Sink


if TYPE_CHECKING:
    from ..typeshed import XmlElement


class TrivialElementModel(kit.LoadModelBase[str]):
    def __init__(self, tag: str):
        self.tag = tag

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == self.tag

    def load(self, log: Log, xe: XmlElement) -> str | None:
        kit.check_no_attrib(log, xe)
        kit.check_no_content(log, xe)
        return self.tag


class TagMold:
    def __init__(
        self,
        tag: str | StartTag,
        *,
        optional_attrib: set[str] = set(),
        jats_name: str | None = None,
    ):
        self.tag = StartTag(tag)
        self._ok_attrib_keys = optional_attrib | set(self.tag.attrib.keys())
        self.jats_name = jats_name

    def match(self, x: StartTag | XmlElement) -> bool:
        if self.jats_name is not None and x.tag == self.jats_name:
            return True
        return self.tag.issubset(x)

    def copy_attributes(self, log: Log, xe: XmlElement, dest: Element) -> None:
        kit.check_no_attrib(log, xe, self._ok_attrib_keys)
        for key, value in xe.attrib.items():
            if key not in self._ok_attrib_keys:
                log(fc.UnsupportedAttribute.issue(xe, key))
            elif key not in self.tag.attrib:
                dest.set_attrib(key, value)


class EmptyElementModel(kit.LoadModelBase[ElementT]):
    def __init__(self, tag_mold: TagMold, factory: Callable[[], ElementT]):
        self.tag_mold = tag_mold
        self.factory = factory

    def match(self, xe: XmlElement) -> bool:
        return self.tag_mold.match(xe)

    def load(self, log: Log, xe: XmlElement) -> ElementT | None:
        ret = self.factory()
        self.tag_mold.copy_attributes(log, xe, ret)
        kit.check_no_content(log, xe)
        return ret


class ParentModel(kit.LoadModelBase[Parent[ParsedT]]):
    def __init__(
        self,
        tag_mold: TagMold,
        content_model: ContentModel[ParsedT],
        factory: Callable[[], Parent[ParsedT]],
    ):
        self.tag_mold = tag_mold
        self.content_model = content_model
        self.factory = factory

    def match(self, xe: XmlElement) -> bool:
        return self.tag_mold.match(xe)

    def load(self, log: Log, xe: XmlElement) -> Parent[ParsedT] | None:
        ret = self.factory()
        self.tag_mold.copy_attributes(log, xe, ret)
        self.content_model.parse_content(log, xe, ret.append)
        return ret


class MarkupBlockModel(ParentModel[str | Element]):
    def __init__(self, inline_model: MixedModel):
        super().__init__(TagMold('div'), inline_model, MarkupBlock)


class ParentModelBase(ParentModel[AppendT], Generic[AppendT]):
    def __init__(self, tag_mold: TagMold, content_model: ContentModel[AppendT]):
        super().__init__(tag_mold, content_model, self.factory)

    @abstractmethod
    def factory(self) -> Parent[AppendT]: ...


class ArrayParentModel(ParentModelBase[Element]):
    def __init__(self, tag_mold: TagMold, child_model: Model[Element]):
        super().__init__(tag_mold, DataContentModel(child_model))

    def factory(self) -> Parent[Element]:
        return ArrayParent(self.tag_mold.tag)


class MixedParentModel(ParentModelBase[str | Element]):
    def factory(self) -> Parent[str | Element]:
        return MixedParent(self.tag_mold.tag)


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

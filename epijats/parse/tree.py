"""Parsing of abstract systax tree elements in ..tree submodule."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from typing import Generic, TYPE_CHECKING

from ..elements import ElementT
from ..tree import (
    AppendT,
    ArrayParentElement,
    BiformElement,
    Element,
    MarkupBlock,
    MarkupElement,
    MixedParentElement,
    Parent,
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


class MarkupBlockModel(kit.LoadModelBase[Element]):
    def __init__(self, inline_model: MixedModel):
        self.inline_model = inline_model

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'div'

    def load(self, log: Log, xe: XmlElement) -> Element | None:
        kit.check_no_attrib(log, xe)
        ret = MarkupBlock()
        self.inline_model.parse_content(log, xe, ret.append)
        return ret


class TagMold:
    def __init__(
        self,
        tag: str | StartTag,
        *,
        optional_attrib: set[str] = set(),
        jats_tag: str | None = None,
    ):
        self.stag = StartTag(tag)
        self._ok_attrib_keys = optional_attrib | set(self.stag.attrib.keys())
        self.jats_tag = jats_tag

    def match(self, x: StartTag | XmlElement) -> bool:
        if self.jats_tag is not None and x.tag == self.jats_tag:
            return True
        return self.stag.issubset(x)

    def copy_attributes(self, log: Log, xe: XmlElement, dest: Element) -> None:
        kit.check_no_attrib(log, xe, self._ok_attrib_keys)
        kit.copy_ok_attrib_values(log, xe, self._ok_attrib_keys, dest.xml.attrib)


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


class ElementModelBase(kit.LoadModelBase[Element], Generic[AppendT]):
    def __init__(self, tag_mold: TagMold, content_model: ContentModel[AppendT]):
        self.tag_mold = tag_mold
        self.content_model: ContentModel[AppendT] = content_model

    def match(self, xe: XmlElement) -> bool:
        return self.tag_mold.match(xe)

    def load(self, log: Log, xe: XmlElement) -> Element | None:
        ret = self.start(self.tag_mold.stag)
        self.tag_mold.copy_attributes(log, xe, ret)
        self.content_model.parse_content(log, xe, ret.append)
        return ret

    @abstractmethod
    def start(self, stag: StartTag) -> Parent[AppendT]: ...


ArrayParentModelBase = ElementModelBase[Element]


class ItemModel(ArrayParentModelBase):
    def __init__(self, tag_mold: TagMold, child_model: Model[Element]):
        super().__init__(tag_mold, DataContentModel(child_model))

    def start(self, stag: StartTag) -> Parent[Element]:
        return ArrayParentElement(stag)


class MixedParentElementModel(ElementModelBase[str | Element]):
    def start(self, stag: StartTag) -> Parent[str | Element]:
        return MixedParentElement(stag)


class BiformModel(ArrayParentModelBase):
    def start(self, stag: StartTag) -> Parent[Element]:
        return BiformElement(stag)


class MarkupMixedModel(kit.LoadModelBase[Element]):
    def __init__(self, tag_mold: TagMold, content_model: MixedModel):
        self.tag_mold = tag_mold
        self.content_model = content_model

    def match(self, xe: XmlElement) -> bool:
        return self.tag_mold.match(xe)

    def load(self, log: Log, xe: XmlElement) -> Element | None:
        ret = MarkupElement(self.tag_mold.stag)
        self.tag_mold.copy_attributes(log, xe, ret)
        self.content_model.parse_content(log, xe, ret.append)
        return ret


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

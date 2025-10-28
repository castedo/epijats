"""Parsing of abstract systax tree elements in ..tree submodule."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from typing import Generic, TYPE_CHECKING

from .. import condition as fc
from ..tree import (
    AppendT,
    ArrayParentElement,
    BiformElement,
    Element,
    Inline,
    MarkupBlock,
    MarkupElement,
    MixedParentElement,
    MutableMixedContent,
    Parent,
    StartTag,
)

from . import kit
from .content import (
    ContentMold,
    MixedModel,
    MixedModelBase,
    parse_mixed_content,
)
from .kit import Log, ParsedT, Sink


if TYPE_CHECKING:
    from ..typeshed import XmlElement


def check_no_content(log: Log, xe: XmlElement) -> None:
    if xe.text and xe.text.strip():
        log(fc.IgnoredText.issue(xe))
    for s in xe:
        log(fc.ExcessElement.issue(s))
        if s.tail and s.tail.strip():
            log(fc.IgnoredTail.issue(s))


class TrivialElementModel(kit.LoadModelBase[str]):
    def __init__(self, tag: str):
        self.tag = tag

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == self.tag

    def load(self, log: Log, xe: XmlElement) -> str | None:
        kit.check_no_attrib(log, xe)
        check_no_content(log, xe)
        return self.tag


class MarkupBlockModel(kit.LoadModelBase[Element]):
    def __init__(self, inline_model: MixedModel):
        self.inline_model = inline_model

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'div'

    def load(self, log: Log, xe: XmlElement) -> Element | None:
        kit.check_no_attrib(log, xe)
        ret = MarkupBlock()
        parse_mixed_content(log, xe, self.inline_model, ret.append)
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

    def match(self, stag: StartTag) -> bool:
        if self.jats_tag is not None and stag.tag == self.jats_tag:
            return True
        return self.stag.issubset(stag)

    def copy_attributes(self, log: Log, xe: XmlElement, dest: Element) -> None:
        kit.check_no_attrib(log, xe, self._ok_attrib_keys)
        kit.copy_ok_attrib_values(log, xe, self._ok_attrib_keys, dest.xml.attrib)


class TagMoldModelBase(kit.Model[ParsedT]):
    def __init__(self, tag_mold: TagMold):
        self.tag_mold = tag_mold

    def match(self, xe: XmlElement) -> bool:
        stag = StartTag.from_xml(xe)
        return stag is not None and self.tag_mold.match(stag)


class EmptyElementModel(TagMoldModelBase[Element]):
    def __init__(self, tag_mold: TagMold, factory: Callable[[], Element]):
        super().__init__(tag_mold)
        self.factory = factory

    def parse(self, log: Log, xe: XmlElement, sink: Sink[Element]) -> None:
        ret = self.factory()
        self.tag_mold.copy_attributes(log, xe, ret)
        check_no_content(log, xe)
        sink(ret)


class EmptyInlineModel(TagMoldModelBase[str | Inline]):
    def __init__(self, tag_mold: TagMold, factory: Callable[[], Inline]):
        super().__init__(tag_mold)
        self.factory = factory

    def parse(self, log: Log, xe: XmlElement, sink: Sink[str | Inline]) -> None:
        ret = self.factory()
        self.tag_mold.copy_attributes(log, xe, ret)
        check_no_content(log, xe)
        sink(ret)
        if xe.tail:
            sink(xe.tail)


class ElementModelBase(TagMoldModelBase[Element], Generic[AppendT]):
    def __init__(self, tag_mold: TagMold, content_mold: ContentMold[AppendT]):
        super().__init__(tag_mold)
        self.content_mold: ContentMold[AppendT] = content_mold

    def parse(self, log: Log, xe: XmlElement, sink: Sink[Element]) -> None:
        ret = self.start(self.tag_mold.stag)
        self.tag_mold.copy_attributes(log, xe, ret)
        self.content_mold.read(log, xe, ret.append)
        sink(ret)

    @abstractmethod
    def start(self, stag: StartTag) -> Parent[AppendT]: ...


ArrayParentModelBase = ElementModelBase[Element]


class ItemModel(ElementModelBase[Element]):
    def start(self, stag: StartTag) -> Parent[Element]:
        return ArrayParentElement(stag)


class MixedParentElementModel(ElementModelBase[str | Inline]):
    def start(self, stag: StartTag) -> Parent[str | Inline]:
        return MixedParentElement(stag)


class BiformModel(ArrayParentModelBase):
    def start(self, stag: StartTag) -> Parent[Element]:
        return BiformElement(stag)


class MarkupModel(MixedModelBase):
    def __init__(self, mold: TagMold, child_model: MixedModel):
        self.tag_mold = mold
        self.child_model = child_model

    def match(self, xe: XmlElement) -> bool:
        stag = StartTag.from_xml(xe)
        return stag is not None and self.tag_mold.match(stag)

    def load(self, log: Log, xe: XmlElement) -> Inline | None:
        ret = MarkupElement(self.tag_mold.stag)
        if ret is not None:
            self.tag_mold.copy_attributes(log, xe, ret)
            parse_mixed_content(log, xe, self.child_model, ret.append)
            return ret
        return None


class MixedContentBinderBase(kit.Binder[MutableMixedContent]):
    def __init__(self, content_mold: ContentMold[str | Inline]):
        self.content_mold = content_mold

    def parse(self, log: Log, xe: XmlElement, target: MutableMixedContent) -> None:
        kit.check_no_attrib(log, xe)
        if target.blank():
            self.content_mold.read(log, xe, target)
        else:
            log(fc.ExcessElement.issue(xe))


class MixedContentBinder(MixedContentBinderBase):
    def __init__(self, tag: str, content_mold: ContentMold[str | Inline]):
        super().__init__(content_mold)
        self.tag = tag

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == self.tag

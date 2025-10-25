"""Parsing of abstract systax tree elements in ..tree submodule."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from typing import Generic, TYPE_CHECKING

from .. import condition as fc
from ..tree import (
    ArrayContent,
    BiformElement,
    ContentT,
    Element,
    Inline,
    MarkupBlock,
    MarkupElement,
    MixedContent,
    Parent,
    StartTag,
    WhitespaceElement,
)

from . import kit
from .content import (
    ContentMold,
    MixedModel,
    MixedModelBase,
    parse_mixed_content,
)
from .kit import Log


if TYPE_CHECKING:
    from ..typeshed import XmlElement


class EmptyElementModel(kit.TagModelBase[Element]):
    def __init__(
        self,
        tag: str,
        *,
        attrib: set[str] = set(),
        factory: Callable[[], Element] | None = None,
    ):
        super().__init__(tag)
        self.factory = factory
        self._ok_attrib_keys = attrib

    def load(self, log: Log, e: XmlElement) -> Element | None:
        ret = self.factory() if self.factory else WhitespaceElement(self.tag)
        kit.check_no_attrib(log, e, self._ok_attrib_keys)
        kit.copy_ok_attrib_values(log, e, self._ok_attrib_keys, ret.xml.attrib)
        if e.text and e.text.strip():
            log(fc.IgnoredText.issue(e))
        for s in e:
            if s.tail and s.tail.strip():
                log(fc.IgnoredTail.issue(s))
        return ret


class MarkupBlockModel(kit.LoadModelBase[Element]):
    def __init__(self, inline_model: MixedModel):
        self.inline_model = inline_model

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == 'div'

    def load(self, log: Log, xe: XmlElement) -> Element | None:
        kit.check_no_attrib(log, xe)
        ret = MarkupBlock()
        parse_mixed_content(log, xe, self.inline_model, ret.content)
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


class ElementModelBase(kit.LoadModelBase[Element], Generic[ContentT]):
    def __init__(self, mold: TagMold, content_mold: ContentMold[ContentT]):
        self.tag_mold = mold
        self.content_mold: ContentMold[ContentT] = content_mold

    def match(self, xe: XmlElement) -> bool:
        stag = StartTag.from_xml(xe)
        return stag is not None and self.tag_mold.match(stag)

    def load(self, log: Log, xe: XmlElement) -> Element | None:
        ret = self.start(self.tag_mold.stag)
        if ret is not None:
            self.tag_mold.copy_attributes(log, xe, ret)
            self.content_mold.read(log, xe, ret.content)
            return ret
        return None

    @abstractmethod
    def start(self, stag: StartTag) -> Parent[ContentT] | None: ...


class ItemModel(ElementModelBase[ContentT]):
    def start(self, stag: StartTag) -> Parent[ContentT] | None:
        return Parent(stag, self.content_mold.content_type())


class BiformModel(ElementModelBase[ArrayContent]):
    def start(self, stag: StartTag) -> Parent[ArrayContent] | None:
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
            parse_mixed_content(log, xe, self.child_model, ret.content)
            return ret
        return None


class MixedContentBinderBase(kit.BinderBase[MixedContent]):
    def __init__(self, content_mold: ContentMold[MixedContent]):
        self.content_mold = content_mold

    def read(self, log: Log, xe: XmlElement, target: MixedContent) -> None:
        kit.check_no_attrib(log, xe)
        if target.blank():
            self.content_mold.read(log, xe, target)
        else:
            log(fc.ExcessElement.issue(xe))


class MixedContentBinder(MixedContentBinderBase):
    def __init__(self, tag: str, content_mold: ContentMold[MixedContent]):
        super().__init__(content_mold)
        self.tag = tag

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == self.tag

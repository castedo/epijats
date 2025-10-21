"""Parsing of abstract systax tree elements in ..tree submodule."""

from __future__ import annotations

from abc import abstractmethod
from typing import Generic, TYPE_CHECKING

from .. import condition as fc
from ..tree import (
    ContentT,
    Element,
    ElementT,
    HtmlVoidElement,
    Inline,
    MarkupBlock,
    MixedContent,
    Parent,
    ParentInline,
    ParentItem,
    PureElement,
    StartTag,
    WhitespaceElement,
)

from . import kit
from .content import ContentMold, parse_mixed_content
from .kit import Log, Model


if TYPE_CHECKING:
    from ..typeshed import XmlElement


class EmptyElementModel(kit.TagModelBase[Element]):
    def __init__(self, tag: str, *, is_html_tag: bool, attrib: set[str] = set()):
        super().__init__(tag)
        self.is_html_tag = is_html_tag
        self._ok_attrib_keys = attrib

    def load(self, log: Log, e: XmlElement) -> Element | None:
        klass = HtmlVoidElement if self.is_html_tag else WhitespaceElement
        ret = klass(self.tag)
        kit.check_no_attrib(log, e, self._ok_attrib_keys)
        kit.copy_ok_attrib_values(log, e, self._ok_attrib_keys, ret.xml.attrib)
        if e.text and e.text.strip():
            log(fc.IgnoredText.issue(e))
        for s in e:
            if s.tail and s.tail.strip():
                log(fc.IgnoredTail.issue(s))
        return ret


class MarkupBlockModel(kit.LoadModel[Element]):
    def __init__(self, inline_model: Model[Inline]):
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

    def copy_attributes(self, log: Log, xe: XmlElement, dest: PureElement) -> None:
        kit.check_no_attrib(log, xe, self._ok_attrib_keys)
        kit.copy_ok_attrib_values(log, xe, self._ok_attrib_keys, dest.xml.attrib)


class ElementModelBase(kit.LoadModel[ElementT], Generic[ElementT, ContentT]):
    def __init__(self, mold: TagMold, content_mold: ContentMold[ContentT]):
        self.tag_mold = mold
        self.content_mold: ContentMold[ContentT] = content_mold

    def match(self, xe: XmlElement) -> bool:
        stag = StartTag.from_xml(xe)
        return stag is not None and self.tag_mold.match(stag)

    def load(self, log: Log, xe: XmlElement) -> ElementT | None:
        ret = self.start(self.tag_mold.stag, self.content_mold.content_type)
        if ret is not None:
            self.tag_mold.copy_attributes(log, xe, ret.this)
            self.content_mold.read(log, xe, ret.content)
            return ret.this
        return None

    @abstractmethod
    def start(
        self, stag: StartTag, content: type[ContentT]
    ) -> Parent[ElementT, ContentT] | None: ...


class InlineModel(ElementModelBase[Inline, ContentT]):
    def start(
        self, stag: StartTag, content: type[ContentT]
    ) -> Parent[Inline, ContentT] | None:
        return ParentInline(stag, content())


class ItemModel(ElementModelBase[Element, ContentT]):
    def start(
        self, stag: StartTag, content: type[ContentT]
    ) -> Parent[Element, ContentT] | None:
        return ParentItem(stag, content())


class MixedContentModelBase(kit.MonoModel[MixedContent]):
    def __init__(self, content_mold: ContentMold[MixedContent]):
        self.content_mold = content_mold

    @property
    def parsed_type(self) -> type[MixedContent]:
        return self.content_mold.content_type

    def read(self, log: Log, xe: XmlElement, target: MixedContent) -> None:
        kit.check_no_attrib(log, xe)
        if target.blank():
            self.content_mold.read(log, xe, target)
        else:
            log(fc.ExcessElement.issue(xe))


class MixedContentModel(MixedContentModelBase):
    def __init__(self, tag: str, content_mold: ContentMold[MixedContent]):
        super().__init__(content_mold)
        self.tag = tag

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == self.tag

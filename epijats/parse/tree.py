"""Parsing of abstract systax tree elements in ..tree submodule."""

from __future__ import annotations

from abc import abstractmethod
from typing import Generic, Protocol, TYPE_CHECKING, TypeAlias

from .. import condition as fc
from ..tree import (
    ArrayContent,
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
from .content import parse_array_content
from .kit import Log, Model, Sink


if TYPE_CHECKING:
    from ..typeshed import XmlElement


def parse_mixed_content(
    log: Log, e: XmlElement, emodel: Model[Inline], dest: MixedContent
) -> None:
    dest.append_text(e.text)
    eparser = emodel.bound_parser(log, dest.append)
    for s in e:
        if not eparser.parse_element(s):
            log(fc.UnsupportedElement.issue(s))
            parse_mixed_content(log, s, emodel, dest)
            dest.append_text(s.tail)


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


class ContentMold(Protocol, Generic[ContentT]):
    content_type: type[ContentT]

    def read(self, log: Log, xe: XmlElement, dest: ContentT) -> None: ...


class MixedContentMold(ContentMold[MixedContent]):
    def __init__(self, child_model: Model[Inline]):
        self.content_type = MixedContent
        self.child_model = child_model

    def read(self, log: Log, xe: XmlElement, dest: MixedContent) -> None:
        parse_mixed_content(log, xe, self.child_model, dest)


ArrayContentMold: TypeAlias = ContentMold[ArrayContent]


class DataContentMold(ArrayContentMold):
    def __init__(self, child_model: Model[Element]):
        self.content_type = ArrayContent
        self.child_model = child_model

    def read(self, log: Log, xe: XmlElement, dest: ArrayContent) -> None:
        parse_array_content(log, xe, self.child_model, dest.append)


class PendingMarkupItem:
    def __init__(
        self, item_type: type[Parent[Element, MixedContent]], dest: Sink[Element]
    ):
        self.item_type = item_type
        self.dest = dest
        self._pending: Parent[Element, MixedContent] | None = None

    def close(self) -> None:
        if self._pending is not None and not self._pending.content.blank():
            self.dest(self._pending.this)
            self._pending = None

    @property
    def content(self) -> MixedContent:
        if self._pending is None:
            self._pending = self.item_type()
        return self._pending.content


class RollContentMold(DataContentMold):
    def __init__(self, block_model: Model[Element], inline_model: Model[Inline]):
        super().__init__(block_model | MarkupBlockModel(inline_model))
        self.inline_model = inline_model

    def read(self, log: Log, xe: XmlElement, dest: ArrayContent) -> None:
        pending = PendingMarkupItem(MarkupBlock, dest.append)
        if xe.text and xe.text.strip():
            pending.content.append_text(xe.text)
        for s in xe:
            tail = s.tail
            s.tail = None
            if self.child_model.match(s):
                pending.close()
                self.child_model.parse(log, s, dest.append)
            else:
                if self.inline_model.match(s):
                    self.inline_model.parse(log, s, pending.content.append)
                else:
                    log(fc.UnsupportedElement.issue(s))
            if tail and tail.strip():
                pending.content.append_text(tail)
        pending.close()
        return None


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
    def __init__(self, child_model: Model[Inline]):
        self.child_model = child_model

    @property
    def parsed_type(self) -> type[MixedContent]:
        return MixedContent

    def read(self, log: Log, xe: XmlElement, target: MixedContent) -> None:
        kit.check_no_attrib(log, xe)
        if target.blank():
            parse_mixed_content(log, xe, self.child_model, target)
        else:
            log(fc.ExcessElement.issue(xe))


class MixedContentModel(MixedContentModelBase):
    def __init__(self, tag: str, child_model: Model[Inline]):
        super().__init__(child_model)
        self.tag = tag

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == self.tag

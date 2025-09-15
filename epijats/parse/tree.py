"""Parsing of abstract systax tree elements in ..tree submodule."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import condition as fc
from ..tree import (
    DataElement,
    Element,
    EmptyElement,
    MarkupElement,
    MixedContent,
    StartTag,
)

from . import kit
from .content import ArrayContentSession
from .kit import Log, Model


if TYPE_CHECKING:
    from ..xml import XmlElement


def parse_mixed_content(
    log: Log, e: XmlElement, emodel: Model[Element], dest: MixedContent
) -> None:
    dest.append_text(e.text)
    eparser = emodel.bound_parser(log, dest.append)
    for s in e:
        if not eparser.parse_element(s):
            log(fc.UnsupportedElement.issue(s))
            parse_mixed_content(log, s, emodel, dest)
            dest.append_text(s.tail)


class EmptyElementModel(kit.TagModelBase[Element]):
    def __init__(self, tag: str, *, attrib: set[str] = set()):
        super().__init__(tag)
        self._ok_attrib_keys = attrib

    def load(self, log: Log, e: XmlElement) -> Element | None:
        ret = EmptyElement(self.tag)
        kit.copy_ok_attrib_values(log, e, self._ok_attrib_keys, ret.xml.attrib)
        return ret


class DataElementModel(kit.LoadModel[Element]):
    def __init__(
        self,
        tag: str | StartTag,
        content_model: Model[Element],
        *,
        optional_attrib: set[str] = set(),
        jats_tag: str | None = None,
    ):
        self.stag = StartTag(tag)
        self.content_model = content_model
        self._ok_attrib_keys = optional_attrib | set(self.stag.attrib.keys())
        self.jats_tag = jats_tag

    def match(self, xe: XmlElement) -> bool:
        if self.jats_tag is not None and xe.tag == self.jats_tag:
            return True
        return kit.match_start_tag(xe, self.stag)

    def load(self, log: Log, xe: XmlElement) -> Element | None:
        ret = DataElement(self.stag.tag)
        kit.copy_ok_attrib_values(log, xe, self._ok_attrib_keys, ret.xml.attrib)
        sess = ArrayContentSession(log)
        sess.bind(self.content_model, ret.append)
        sess.parse_content(xe)
        return ret


class TextElementModel(kit.LoadModel[Element]):
    def __init__(
        self,
        tag: str,
        content_model: Model[Element],
        *,
        jats_tag: str | None = None,
    ):
        self.tag = tag
        self.content_model = content_model
        self.jats_tag = jats_tag

    def match(self, xe: XmlElement) -> bool:
        if self.jats_tag is not None and xe.tag == self.jats_tag:
            return True
        return xe.tag == self.tag

    def check(self, log: Log, e: XmlElement) -> None:
        kit.check_no_attrib(log, e)

    def load(self, log: Log, e: XmlElement) -> Element | None:
        self.check(log, e)
        ret = MarkupElement(self.tag)
        parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


class MixedContentModelBase(kit.MonoModel[MixedContent]):
    def __init__(self, child_model: Model[Element]):
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
    def __init__(self, tag: str, child_model: Model[Element]):
        super().__init__(child_model)
        self.tag = tag

    def match(self, xe: XmlElement) -> bool:
        return xe.tag == self.tag

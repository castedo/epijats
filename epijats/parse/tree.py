from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

from .. import condition as fc
from ..tree import (
    DataElement,
    Element,
    EmptyElement,
    MarkupElement,
    MixedContent,
)

from . import kit
from .kit import (
    IssueCallback,
    Loader,
)

if TYPE_CHECKING:
    from ..xml import XmlElement


EModel: TypeAlias = kit.Model[Element]


def parse_mixed_content(
    log: IssueCallback, e: XmlElement, emodel: EModel, dest: MixedContent
) -> None:
    dest.append_text(e.text)
    eparser = emodel.bind(log, dest.append)
    for s in e:
        if not eparser.parse_element(s):
            log(fc.UnsupportedElement.issue(s))
            parse_mixed_content(log, s, emodel, dest)
            dest.append_text(s.tail)


class EmptyElementModel(kit.TagModelBase[Element]):
    def __init__(self, tag: str, *, attrib: set[str] = set()):
        super().__init__(tag)
        self._ok_attrib_keys = attrib

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
        ret = EmptyElement(self.tag)
        kit.copy_ok_attrib_values(log, e, self._ok_attrib_keys, ret.xml.attrib)
        return ret


class DataElementModel(kit.TagModelBase[Element]):
    def __init__(self, tag: str, content_model: EModel, *, attrib: set[str] = set()):
        super().__init__(tag)
        self.content_model = content_model
        self._ok_attrib_keys = attrib

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
        ret = DataElement(self.tag)
        kit.copy_ok_attrib_values(log, e, self._ok_attrib_keys, ret.xml.attrib)
        self.content_model.bind(log, ret.append).parse_array_content(e)
        return ret


class TextElementModel(kit.ModelBase[Element]):
    def __init__(self, tags: set[str], content_model: EModel):
        self._tags = tags
        self.content_model = content_model

    def match(self, xe: XmlElement) -> bool:
        return xe.tag in self._tags

    def check(self, log: IssueCallback, e: XmlElement) -> None:
        kit.check_no_attrib(log, e)

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
        ret = None
        if isinstance(e.tag, str) and e.tag in self._tags:
            self.check(log, e)
            ret = MarkupElement(e.tag)
            parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


class MixedContentLoader(Loader[MixedContent]):
    def __init__(self, model: EModel):
        self.model = model

    def __call__(self, log: IssueCallback, e: XmlElement) -> MixedContent | None:
        kit.check_no_attrib(log, e)
        ret = MixedContent()
        parse_mixed_content(log, e, self.model, ret)
        return ret


class MixedContentBinder(kit.Reader[MixedContent]):
    def __init__(self, tag: str, content_model: EModel):
        super().__init__(tag)
        self.content_model = content_model

    def read(self, log: IssueCallback, xe: XmlElement, dest: MixedContent) -> None:
        kit.check_no_attrib(log, xe)
        if dest.blank():
            parse_mixed_content(log, xe, self.content_model, dest)
        else:
            log(fc.ExcessElement.issue(xe))

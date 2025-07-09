from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Iterable, TypeAlias

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
from .kit import (
    ReaderBinderParser,
    Binder,
    IssueCallback,
    Loader,
    Model,
    Parser,
    Sink,
)

if TYPE_CHECKING:
    from ..xml import XmlElement


EModel: TypeAlias = Model[Element]


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


class ElementModelBase(Model[Element]):
    @property
    @abstractmethod
    def stags(self) -> Iterable[StartTag]: ...

    @property
    def tags(self) -> Iterable[str]:
        return (s.tag for s in self.stags)

    @abstractmethod
    def load(self, log: IssueCallback, e: XmlElement) -> Element | None: ...

    def bind(self, log: IssueCallback, dest: Sink[Element]) -> Parser:
        return ReaderBinderParser(log, dest, self.stags, self.read)

    def read(self, log: IssueCallback, e: XmlElement, dest: Sink[Element]) -> bool:
        parsed = self.load(log, e)
        if parsed is not None:
            assert isinstance(parsed, Element)
            if e.tail:
                parsed.tail = e.tail
            dest(parsed)
        return parsed is not None


class TagElementModelBase(ElementModelBase):
    def __init__(self, stag: str | StartTag):
        self.stag = StartTag(stag)

    @property
    def tag(self) -> str:
        return self.stag.tag

    @property
    def stags(self) -> Iterable[StartTag]:
        return (self.stag,)


class EmptyElementModel(TagElementModelBase):
    def __init__(self, tag: str, *, attrib: set[str] = set()):
        super().__init__(tag)
        self._ok_attrib_keys = attrib

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
        ret = EmptyElement(self.tag)
        kit.copy_ok_attrib_values(log, e, self._ok_attrib_keys, ret.xml.attrib)
        return ret


class DataElementModel(TagElementModelBase):
    def __init__(self, tag: str, content_model: EModel, *, attrib: set[str] = set()):
        super().__init__(tag)
        self.content_model = content_model
        self._ok_attrib_keys = attrib

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
        ret = DataElement(self.tag)
        kit.copy_ok_attrib_values(log, e, self._ok_attrib_keys, ret.xml.attrib)
        self.content_model.bind(log, ret.append).parse_array_content(e)
        return ret


class TextElementModel(ElementModelBase):
    def __init__(self, tags: set[str], content_model: EModel):
        self._tags = tags
        self.content_model = content_model

    @property
    def stags(self) -> Iterable[StartTag]:
        return (StartTag(tag) for tag in self._tags)

    def check(self, log: IssueCallback, e: XmlElement) -> None:
        kit.check_no_attrib(log, e)

    def load(self, log: IssueCallback, e: XmlElement) -> Element | None:
        ret = None
        if isinstance(e.tag, str) and e.tag in self._tags:
            self.check(log, e)
            ret = MarkupElement(e.tag)
            parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


class MixedContentParser(Parser):
    def __init__(self, log: IssueCallback, dest: MixedContent, model: EModel, tag: str):
        super().__init__(log)
        self.dest = dest
        self.model = model
        self.tag = tag

    def match(self, tag: str, attrib: kit.AttribView) -> kit.ParseFunc | None:
        return self._parse if tag == self.tag else None

    def _parse(self, e: XmlElement) -> bool:
        self.check_no_attrib(e)
        if self.dest.blank():
            parse_mixed_content(self.log, e, self.model, self.dest)
        else:
            self.log(fc.ExcessElement.issue(e))
        return True


class MixedContentLoader(Loader[MixedContent]):
    def __init__(self, model: EModel):
        self.model = model

    def __call__(self, log: IssueCallback, e: XmlElement) -> MixedContent | None:
        kit.check_no_attrib(log, e)
        ret = MixedContent()
        parse_mixed_content(log, e, self.model, ret)
        return ret


class MixedContentBinder(Binder[MixedContent]):
    def __init__(self, tag: str, content_model: EModel):
        self.tag = tag
        self.content_model = content_model

    def bind(self, log: IssueCallback, dest: MixedContent) -> Parser:
        return MixedContentParser(log, dest, self.content_model, self.tag)

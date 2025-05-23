from __future__ import annotations

from abc import abstractmethod
from typing import Iterable, TypeAlias

from lxml import etree

from .. import condition as fc
from ..tree import DataElement, Element, MarkupElement, MixedContent, StartTag

from . import kit
from .kit import (
    AttribView,
    ReaderBinderParser,
    Binder,
    IssueCallback,
    Loader,
    Model,
    Parser,
    Sink,
)


EModel: TypeAlias = Model[Element]


def parse_mixed_content(
    log: IssueCallback, e: etree._Element, emodel: EModel, dest: MixedContent
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
    def load(self, log: IssueCallback, e: etree._Element) -> Element | None: ...

    def bind(self, log: IssueCallback, dest: Sink[Element]) -> Parser:
        return ReaderBinderParser(log, dest, self.stags, self.read)

    def read(self, log: IssueCallback, e: etree._Element, dest: Sink[Element]) -> bool:
        parsed = self.load(log, e)
        if parsed is not None:
            if isinstance(parsed, Element) and e.tail:
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


class DataElementModel(TagElementModelBase):
    def __init__(self, tag: str, content_model: EModel):
        super().__init__(tag)
        self.content_model = content_model

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        kit.check_no_attrib(log, e)
        ret = DataElement(self.tag)
        self.content_model.bind(log, ret.append).parse_array_content(e)
        return ret


class HtmlDataElementModel(DataElementModel):
    def __init__(self, tag: str, content_model: EModel, html_tag: str | None = None):
        super().__init__(tag, content_model)
        self.html = StartTag(html_tag or tag)

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        ret = super().load(log, e)
        if ret:
            ret.html = self.html
        return ret


class TextElementModel(ElementModelBase):
    def __init__(self, tagmap: dict[str, str], content_model: EModel | bool = True):
        self.tagmap = tagmap
        self.content_model: EModel | None = None
        if content_model:
            self.content_model = self if content_model == True else content_model

    @property
    def stags(self) -> Iterable[StartTag]:
        return (StartTag(tag) for tag in self.tagmap)

    def load(self, log: IssueCallback, e: etree._Element) -> Element | None:
        ret = None
        if isinstance(e.tag, str) and e.tag in self.tagmap:
            kit.check_no_attrib(log, e)
            html_tag = self.tagmap[e.tag]
            ret = MarkupElement(e.tag)
            ret.html = StartTag(html_tag)
            if self.content_model:
                parse_mixed_content(log, e, self.content_model, ret.content)
        return ret


class MixedContentParser(Parser):
    def __init__(self, log: IssueCallback, dest: MixedContent, model: EModel, tag: str):
        super().__init__(log)
        self.dest = dest
        self.model = model
        self.tag = tag

    def match(self, tag: str, attrib: AttribView) -> kit.ParseFunc | None:
        return self._parse if tag == self.tag else None

    def _parse(self, e: etree._Element) -> bool:
        self.check_no_attrib(e)
        if self.dest.blank():
            parse_mixed_content(self.log, e, self.model, self.dest)
        else:
            self.log(fc.ExcessElement.issue(e))
        return True


class MixedContentLoader(Loader[MixedContent]):
    def __init__(self, model: EModel):
        self.model = model

    def __call__(self, log: IssueCallback, e: etree._Element) -> MixedContent | None:
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

"""Parsing of XML content."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Generic, TYPE_CHECKING

from .. import condition as fc
from . import kit
from .kit import (
    Binder,
    DestT,
    Log,
    MonoModel,
    Model,
    ParsedT,
    Parser,
)

if TYPE_CHECKING:
    from ..xml import XmlElement


def prep_array_elements(log: Log, e: XmlElement) -> None:
    if e.text and e.text.strip():
        log(fc.IgnoredText.issue(e))
    for s in e:
        if s.tail and s.tail.strip():
            log(fc.IgnoredTail.issue(s))
        s.tail = None


class ArrayContentSession:
    """Parsing session for array (non-mixed, data-oriented) XML content."""

    def __init__(self, log: Log):
        self.log = log
        self._parsers: list[Parser] = []

    def bind(self, binder: Binder[DestT], dest: DestT) -> None:
        self._parsers.append(binder.bound_parser(self.log, dest))

    def bind_mono(self, model: MonoModel[ParsedT], target: ParsedT) -> None:
        self._parsers.append(model.mono_parser(self.log, target))

    def bind_once(self, binder: Binder[DestT], dest: DestT) -> None:
        once = kit.OnlyOnceBinder(binder)
        self._parsers.append(once.bound_parser(self.log, dest))

    def one(self, model: Model[ParsedT]) -> kit.Outcome[ParsedT]:
        ret = kit.SinkDestination[ParsedT]()
        once = kit.OnlyOnceBinder(model)
        self._parsers.append(once.bound_parser(self.log, ret))
        return ret

    def every(self, model: Model[ParsedT]) -> Sequence[ParsedT]:
        ret: list[ParsedT] = list()
        parser = model.bound_parser(self.log, ret.append)
        self._parsers.append(parser)
        return ret

    def parse_content(self, e: XmlElement) -> None:
        prep_array_elements(self.log, e)
        for s in e:
            if not any(p.parse_element(s) for p in self._parsers):
                self.log(fc.UnsupportedElement.issue(s))


class ContentBinder(ABC, Generic[DestT]):
    def __init__(self, dest_type: type[DestT]):
        self.dest_type = dest_type

    @abstractmethod
    def binds(self, sess: ArrayContentSession, dest: DestT) -> None: ...


class MergedElementsContentBinder(ContentBinder[DestT]):
    def __init__(self, child_model: MonoModel[DestT]) -> None:
        super().__init__(child_model.parsed_type)
        self.child_model = child_model

    def binds(self, sess: ArrayContentSession, dest: DestT) -> None:
        sess.bind_mono(self.child_model, dest)


class ContentInElementModelBase(kit.MonoModel[ParsedT]):
    def __init__(self, content: ContentBinder[ParsedT]):
        self.content = content

    @property
    def parsed_type(self) -> type[ParsedT]:
        return self.content.dest_type

    def check(self, log: Log, e: XmlElement) -> None:
        kit.check_no_attrib(log, e)

    def read(self, log: Log, xe: XmlElement, target: ParsedT) -> None:
        self.check(log, xe)
        sess = ArrayContentSession(log)
        self.content.binds(sess, target)
        sess.parse_content(xe)


class ContentInElementModel(kit.TagMonoModelBase[ParsedT]):
    def __init__(self, tag: str, content: ContentBinder[ParsedT]):
        super().__init__(tag)
        self.content = content

    @property
    def parsed_type(self) -> type[ParsedT]:
        return self.content.dest_type

    def read(self, log: Log, xe: XmlElement, target: ParsedT) -> None:
        kit.check_no_attrib(log, xe, self.stag.attrib.keys())
        sess = ArrayContentSession(log)
        self.content.binds(sess, target)
        sess.parse_content(xe)

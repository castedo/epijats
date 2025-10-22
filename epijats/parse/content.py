"""Parsing of XML content."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Generic, Protocol, TYPE_CHECKING, TypeAlias

from .. import condition as fc
from . import kit
from ..tree import (
    ArrayContent,
    ContentT,
    Element,
    Inline,
    MarkupBlock,
    MixedContent,
    Parent,
)
from .kit import (
    Binder,
    DestT,
    Log,
    MonoModel,
    Model,
    ParsedT,
    Parser,
    Sink,
)

if TYPE_CHECKING:
    from ..typeshed import XmlElement


def parse_array_content(
    log: Log, e: XmlElement, parsers: Iterable[Parser] | Parser
) -> None:
    if isinstance(parsers, Parser):
        parsers = [parsers]
    if e.text and e.text.strip():
        log(fc.IgnoredText.issue(e))
    for s in e:
        tail = s.tail
        s.tail = None
        if not any(p.parse_element(s) for p in parsers):
            log(fc.UnsupportedElement.issue(s))
        if tail and tail.strip():
            log(fc.IgnoredTail.issue(s))


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
        parse_array_content(self.log, e, self._parsers)


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


class ContentMold(Protocol, Generic[ContentT]):
    content_type: type[ContentT]

    def read(self, log: Log, xe: XmlElement, dest: ContentT) -> None: ...


class MixedContentMold(ContentMold[MixedContent]):
    def __init__(self, child_model: Model[Inline]):
        self.content_type = MixedContent
        self.child_model = child_model

    def read(self, log: Log, xe: XmlElement, dest: MixedContent) -> None:
        parse_mixed_content(log, xe, self.child_model, dest)


class SubElementMixedContentMold(ContentMold[MixedContent]):
    def __init__(self, child_model: kit.MonoModel[MixedContent]):
        self.content_type = MixedContent
        self.child_model = child_model

    def read(self, log: Log, xe: XmlElement, dest: MixedContent) -> None:
        parser = self.child_model.mono_parser(log, dest)
        parse_array_content(log, xe, parser)


ArrayContentMold: TypeAlias = ContentMold[ArrayContent]


class DataContentMold(ArrayContentMold):
    def __init__(self, child_model: Model[Element]):
        self.content_type = ArrayContent
        self.child_model = child_model

    def read(self, log: Log, xe: XmlElement, dest: ArrayContent) -> None:
        parser = self.child_model.bound_parser(log, dest.append)
        parse_array_content(log, xe, parser)


class PendingMarkupBlock:
    def __init__(
        self, dest: Sink[Element], init: Parent[Element, MixedContent] | None = None
    ):
        self.dest = dest
        self._pending = init

    def close(self) -> bool:
        if self._pending is not None and not self._pending.content.blank():
            self.dest(self._pending.this)
            self._pending = None
            return True
        return False

    @property
    def content(self) -> MixedContent:
        if self._pending is None:
            self._pending = MarkupBlock()
        return self._pending.content


class RollContentMold(DataContentMold):
    def __init__(self, block_model: Model[Element], inline_model: Model[Inline]):
        super().__init__(block_model)
        self.inline_model = inline_model

    def read(self, log: Log, xe: XmlElement, dest: ArrayContent) -> None:
        pending = PendingMarkupBlock(dest.append)
        if xe.text and xe.text.strip():
            pending.content.append_text(xe.text)
        for s in xe:
            tail = s.tail
            s.tail = None
            if self.child_model.match(s):
                pending.close()
                self.child_model.parse(log, s, dest.append)
            elif self.inline_model.match(s):
                self.inline_model.parse(log, s, pending.content.append)
            else:
                log(fc.UnsupportedElement.issue(s))
            if tail and tail.strip():
                pending.content.append_text(tail)
        pending.close()
        return None

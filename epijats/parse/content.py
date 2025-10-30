"""Parsing of XML content."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Generic, Protocol, TYPE_CHECKING, TypeAlias

from .. import condition as fc
from . import kit
from ..tree import (
    AppendT,
    Element,
    Inline,
    MarkupBlock,
    MixedParentElement,
)
from .kit import (
    Parser,
    DestT,
    Log,
    Model,
    ParsedT,
    Sink,
)

if TYPE_CHECKING:
    from ..typeshed import XmlContent, XmlElement


def _parse_array_content(
    log: Log, e: XmlElement, parsers: Iterable[BoundParser] | BoundParser
) -> None:
    if isinstance(parsers, BoundParser):
        parsers = [parsers]
    if e.text and e.text.strip():
        log(fc.IgnoredText.issue(e))
    for s in e:
        tail = s.tail
        s.tail = None
        match = False
        for p in parsers:
            if p.match(s):
                p.parse(s)  # does not matter if parser is done parsing or not
                match = True
        if not match:
            log(fc.UnsupportedElement.issue(s))
        if tail and tail.strip():
            log(fc.IgnoredTail.issue(s))


class BoundParser:
    """Same interface as Parser but log and destination are pre-bound."""

    def __init__(self, parser: Parser[DestT], log: Log, dest: DestT):
        self.parser = parser
        self.log = log
        self.dest = dest

    def match(self, xe: XmlElement) -> bool:
        return self.parser.match(xe)

    def parse(self, xe: XmlElement) -> bool:
        return self.parser.parse(self.log, xe, self.dest)


def parse_array_content(
    log: Log, xe: XmlElement, parser: Parser[DestT], dest: DestT
) -> None:
    _parse_array_content(log, xe, BoundParser(parser, log, dest))


class OnlyOnceParser(BoundParser):
    def __init__(self, parser: Parser[DestT], log: Log, dest: DestT):
        super().__init__(parser, log, dest)
        self._parse_done = False

    def parse(self, xe: XmlElement) -> bool:
        if not self._parse_done:
            self._parse_done = self.parser.parse(self.log, xe, self.dest)
        else:
            self.log(fc.ExcessElement.issue(xe))
        return self._parse_done


class ArrayContentSession:
    """Parsing session for array (non-mixed, data-oriented) XML content."""

    def __init__(self, log: Log):
        self.log = log
        self._parsers: list[BoundParser] = []

    def bind(self, parser: Parser[DestT], dest: DestT) -> None:
        self._parsers.append(BoundParser(parser, self.log, dest))

    def bind_once(self, parser: Parser[DestT], dest: DestT) -> None:
        self._parsers.append(OnlyOnceParser(parser, self.log, dest))

    def one(self, model: Model[ParsedT]) -> kit.Outcome[ParsedT]:
        ret = kit.SinkDestination[ParsedT]()
        self.bind_once(model, ret)
        return ret

    def parse_content(self, e: XmlElement) -> None:
        _parse_array_content(self.log, e, self._parsers)


class ContentModel(Protocol, Generic[AppendT]):
    def parse_content(self, log: Log, xc: XmlContent, dest: Sink[AppendT]) -> None: ...


class MixedModel(Model[str | Inline], ContentModel[str | Inline]):
    def parse_content(self, log: Log, xc: XmlContent, dest: Sink[str | Inline]) -> None:
        if xc.text:
            dest(xc.text)
        for s in xc:
            if self.match(s):
                self.parse(log, s, dest)
            else:
                log(fc.UnsupportedElement.issue(s))
                self.parse_content(log, s, dest)
            if s.tail:
                dest(s.tail)

    def __or__(self, model: Model[str | Inline] | Model[Inline]) -> MixedModel:
        ret = UnionMixedModel()
        ret |= self
        ret |= model
        return ret


class UnionMixedModel(MixedModel):
    def __init__(self) -> None:
        self._models = kit.UnionModel[str | Inline]()

    def match(self, xe: XmlElement) -> bool:
        return self._models.match(xe)

    def parse(self, log: Log, xe: XmlElement, sink: Sink[str | Inline]) -> bool:
        return self._models.parse(log, xe, sink)

    def __ior__(self, model: Model[str | Inline] | Model[Inline]) -> UnionMixedModel:
        self._models |= model
        return self


ArrayContentModel: TypeAlias = ContentModel[Element]


class DataContentModel(ArrayContentModel):
    def __init__(self, child_model: Model[Element]):
        self.child_model = child_model

    def parse_content(self, log: Log, xe: XmlElement, sink: Sink[Element]) -> None:
        parse_array_content(log, xe, self.child_model, sink)


class PendingMarkupBlock:
    def __init__(self, dest: Sink[Element], init: MixedParentElement | None = None):
        self.dest = dest
        self._pending = init

    def close(self) -> bool:
        if self._pending is not None and not self._pending.content.blank():
            self.dest(self._pending)
            self._pending = None
            return True
        return False

    def append(self, x: str | Inline) -> None:
        if self._pending is None:
            self._pending = MarkupBlock()
        self._pending.append(x)


class RollContentModel(ArrayContentModel):
    def __init__(self, block_model: Model[Element], inline_model: MixedModel):
        self.block_model = block_model
        self.inline_model = inline_model

    def parse_content(self, log: Log, xe: XmlElement, sink: Sink[Element]) -> None:
        pending = PendingMarkupBlock(sink)
        if xe.text and xe.text.strip():
            pending.append(xe.text)
        for s in xe:
            tail = s.tail
            s.tail = None
            if self.block_model.match(s):
                pending.close()
                self.block_model.parse(log, s, sink)
            elif self.inline_model.match(s):
                self.inline_model.parse(log, s, pending.append)
            else:
                log(fc.UnsupportedElement.issue(s))
            if tail and tail.strip():
                pending.append(tail)
        pending.close()
